from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from pydantic import BaseModel, Field

from pdf_extraction.models import ParsedPdfDocument, SourceProvenance


TERM_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    ("assay", "MIC", re.compile(r"\bMIC\b", re.I)),
    ("assay", "pMIC", re.compile(r"\bpMIC\b", re.I)),
    ("assay", "minimum inhibitory concentration", re.compile(r"minimum\s+inhibitory\s+concentration", re.I)),
    ("bacteria", "Staphylococcus aureus", re.compile(r"Staphylococcus\s+aureus|S\.?\s*aureus", re.I)),
    ("bacteria", "Escherichia coli", re.compile(r"Escherichia\s+coli|E\.?\s*coli", re.I)),
    ("unit", "µg/mL", re.compile(r"µg/mL|μg/mL|ug/mL|mcg/mL|microg/mL", re.I)),
    ("unit", "mg/L", re.compile(r"mg/L", re.I)),
    ("unit", "mmol/L", re.compile(r"mmol/L|mmol/l", re.I)),
    ("compound", "compound id", re.compile(r"\b(?:compound\s+)?\d+[a-z]{1,3}\b", re.I)),
    ("section", "biological activity", re.compile(r"biological\s+activity|antimicrobial|antibacterial", re.I)),
    ("table", "table", re.compile(r"\btable\s+\d+|caption", re.I)),
)

SECTION_HINT_RE = re.compile(
    r"biological\s+activity|antimicrobial|antibacterial|minimum\s+inhibitory|microbiological",
    re.I,
)


class BenzimidazoleEvidence(BaseModel):
    evidence_id: str
    source_file: str
    page: int | None = None
    section: str | None = None
    table_id: str | None = None
    row_id: str | None = None
    source_text: str
    score: float = Field(ge=0.0)
    matched_terms: list[str] = Field(default_factory=list)
    extraction_method: str = "benzimidazole.evidence_selector"
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)


def select_benzimidazole_evidence(document: ParsedPdfDocument, context_characters: int = 600) -> list[BenzimidazoleEvidence]:
    """Deterministically select Benzimidazoles extraction evidence.

    This is a preprocessing filter for extraction, not a chatbot retriever and
    not vector RAG. It keeps enough provenance for a later LLM or validator to
    tie each prediction back to a source page/table/row.
    """
    selected: list[BenzimidazoleEvidence] = []
    seen: set[tuple[str, int | None, str | None, str | None, str]] = set()

    for table in document.tables:
        header = " | ".join(cell for row in table.rows[:2] for cell in row if cell)
        for row_index, row in enumerate(table.rows):
            row_text = " | ".join(cell for cell in row if cell)
            text = f"{header}\n{row_text}" if header and row_index > 1 else row_text
            evidence = _build_evidence(
                source=table.source,
                source_text=text,
                evidence_id=f"table-{len(selected) + 1}",
                row_id=str(row_index),
            )
            if evidence is not None:
                key = _dedupe_key(evidence)
                if key not in seen:
                    selected.append(evidence)
                    seen.add(key)

    for block_index, block in enumerate(document.text_blocks):
        block_text = block.text.strip()
        if not block_text:
            continue
        windows = _candidate_text_windows(block_text, context_characters)
        for window_index, window in enumerate(windows):
            evidence = _build_evidence(
                source=block.source,
                source_text=window,
                evidence_id=f"text-{block_index + 1}-{window_index + 1}",
            )
            if evidence is not None:
                key = _dedupe_key(evidence)
                if key not in seen:
                    selected.append(evidence)
                    seen.add(key)

    return selected


def write_evidence_bundle(evidence: list[BenzimidazoleEvidence], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([item.model_dump(mode="json") for item in evidence], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def compress_benzimidazole_evidence(
    evidence: list[BenzimidazoleEvidence],
    max_chunks: int | None = None,
) -> list[BenzimidazoleEvidence]:
    """Keep the strongest non-identical evidence chunks before live LLM calls.

    This is intentionally conservative: it does not summarize or rewrite
    evidence text, and it keeps table evidence plus page coverage before
    filling the remaining budget by score. Raw PDF parsing stays unchanged.
    """
    deduped = _dedupe_similar_evidence(evidence)
    if max_chunks is None or max_chunks <= 0 or len(deduped) <= max_chunks:
        return deduped

    selected: list[BenzimidazoleEvidence] = []
    selected_ids: set[str] = set()
    ranked = sorted(deduped, key=_compression_sort_key, reverse=True)

    for item in ranked:
        if item.table_id is not None:
            _append_if_room(item, selected, selected_ids, max_chunks)

    best_by_page: dict[int | None, BenzimidazoleEvidence] = {}
    for item in ranked:
        if item.page not in best_by_page:
            best_by_page[item.page] = item
    for item in best_by_page.values():
        _append_if_room(item, selected, selected_ids, max_chunks)

    for item in ranked:
        _append_if_room(item, selected, selected_ids, max_chunks)
        if len(selected) >= max_chunks:
            break

    selected_order = {item.evidence_id: index for index, item in enumerate(evidence)}
    return sorted(selected, key=lambda item: selected_order.get(item.evidence_id, 0))


def _candidate_text_windows(text: str, context_characters: int) -> list[str]:
    if SECTION_HINT_RE.search(text) and len(text) <= context_characters * 3:
        return [text]
    windows: list[str] = []
    for _category, _term, pattern in TERM_PATTERNS:
        for match in pattern.finditer(text):
            start = max(0, match.start() - context_characters)
            end = min(len(text), match.end() + context_characters)
            windows.append(text[start:end].strip())
    return windows


def _build_evidence(
    source: SourceProvenance,
    source_text: str,
    evidence_id: str,
    row_id: str | None = None,
) -> BenzimidazoleEvidence | None:
    matched_terms = _matched_terms(source_text)
    if not matched_terms:
        return None
    categories = {_category_for_term(term) for term in matched_terms}
    if not ({"assay", "bacteria"} & categories or {"assay", "unit"} <= categories or {"section", "assay"} <= categories):
        return None
    score = _score_terms(matched_terms)
    return BenzimidazoleEvidence(
        evidence_id=evidence_id,
        source_file=source.source_file,
        page=source.page,
        section=source.section,
        table_id=source.table_id,
        row_id=row_id,
        source_text=source_text,
        score=score,
        matched_terms=matched_terms,
        confidence=min(0.95, 0.45 + score / 10),
    )


def _matched_terms(text: str) -> list[str]:
    terms: list[str] = []
    for _category, term, pattern in TERM_PATTERNS:
        if pattern.search(text) and term not in terms:
            terms.append(term)
    return terms


def _category_for_term(term: str) -> str:
    for category, candidate, _pattern in TERM_PATTERNS:
        if candidate == term:
            return category
    return "unknown"


def _score_terms(terms: list[str]) -> float:
    weights = {
        "assay": 3.0,
        "bacteria": 2.0,
        "unit": 1.5,
        "compound": 1.0,
        "section": 1.0,
        "table": 0.5,
    }
    return sum(weights.get(_category_for_term(term), 0.25) for term in terms)


def _dedupe_key(evidence: BenzimidazoleEvidence) -> tuple[str, int | None, str | None, str | None, str]:
    return (
        evidence.source_file,
        evidence.page,
        evidence.table_id,
        evidence.row_id,
        re.sub(r"\s+", " ", evidence.source_text.strip()),
    )


def _dedupe_similar_evidence(evidence: list[BenzimidazoleEvidence]) -> list[BenzimidazoleEvidence]:
    groups: dict[tuple[str, int | None, str | None, str | None, str], list[BenzimidazoleEvidence]] = defaultdict(list)
    for item in evidence:
        groups[_similarity_key(item)].append(item)
    representatives = [max(items, key=_compression_sort_key) for items in groups.values()]
    original_order = {item.evidence_id: index for index, item in enumerate(evidence)}
    return sorted(representatives, key=lambda item: original_order.get(item.evidence_id, 0))


def _similarity_key(evidence: BenzimidazoleEvidence) -> tuple[str, int | None, str | None, str | None, str]:
    normalized = re.sub(r"\W+", " ", evidence.source_text.lower()).strip()
    fingerprint_terms = " ".join(sorted(set(re.findall(r"\b\d+[a-z]{0,3}\b|mic|pmic|aureus|coli", normalized))))
    return (
        evidence.source_file,
        evidence.page,
        evidence.table_id,
        evidence.row_id,
        fingerprint_terms or normalized[:240],
    )


def _compression_sort_key(evidence: BenzimidazoleEvidence) -> tuple[int, float, int, int]:
    terms = set(evidence.matched_terms)
    has_assay = int(bool({"MIC", "pMIC", "minimum inhibitory concentration"} & terms))
    has_bacteria = int(bool({"Staphylococcus aureus", "Escherichia coli"} & terms))
    has_unit = int(bool({"µg/mL", "mg/L", "mmol/L"} & terms))
    has_compound = int("compound id" in terms)
    table_bonus = int(evidence.table_id is not None)
    completeness = has_assay + has_bacteria + has_unit + has_compound + table_bonus
    return (completeness, evidence.score, table_bonus, -len(evidence.source_text))


def _append_if_room(
    item: BenzimidazoleEvidence,
    selected: list[BenzimidazoleEvidence],
    selected_ids: set[str],
    max_chunks: int,
) -> None:
    if len(selected) < max_chunks and item.evidence_id not in selected_ids:
        selected.append(item)
        selected_ids.add(item.evidence_id)
