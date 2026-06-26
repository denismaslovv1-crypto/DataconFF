from __future__ import annotations

import re

from datacon_workflow.domains.benzimidazoles import BenzimidazoleRawRecord, EvidenceProvenance, MISSING_VALUE
from datacon_workflow.extraction.evidence_builder import EvidenceChunk


ASSAY_RE = re.compile(
    r"\b(?P<type>p?MIC)\b[^<>=\d]{0,40}(?P<relation><=|>=|<|>|=)?\s*(?P<value>\d+(?:\.\d+)?(?:\s*[-–]\s*\d+(?:\.\d+)?)?)\s*(?P<unit>µg/mL|μg/mL|ug/mL|mcg/mL|microg/mL|mg/L|mmol/L|mmol/l)?",
    re.I,
)
COMPOUND_RE = re.compile(r"\b(?:compound\s+)?(?P<id>\d+[a-z]{0,3}|[A-Z]\d{1,3})\b", re.I)
BACTERIA_RE = re.compile(r"(?P<name>S\.\s*aureus|Staph\.\s*aureus|Staphylococcus\s+aureus|E\.\s*coli|Escherichia\s+coli)", re.I)
TABLE_HEADER_RE = re.compile(r"\bMIC\s*\([^)]*\)\s*[cd].*?MRSA\s*MIC", re.I)
TABLE_ROW_RE = re.compile(r"^\s*(?P<id>\d{1,3})\s+.+$", re.M)
NUMBER_RE = re.compile(r"(?<![A-Za-z])(?P<relation>[<>])?\s*(?P<value>\d+(?:\.\d+)?)")


def extract_records(chunks: list[EvidenceChunk]) -> list[BenzimidazoleRawRecord]:
    records: list[BenzimidazoleRawRecord] = []
    table_sources: set[tuple[str, int | None]] = set()
    for chunk in chunks:
        table_records = _extract_mic_table_rows(chunk)
        if table_records:
            records.extend(table_records)
            table_sources.add((chunk.source.source_file, chunk.source.page))

    for chunk in chunks:
        if (chunk.source.source_file, chunk.source.page) in table_sources:
            continue
        bacteria = BACTERIA_RE.findall(chunk.text)
        assays = list(ASSAY_RE.finditer(chunk.text))
        compounds = [match.group("id") for match in COMPOUND_RE.finditer(chunk.text)] or [MISSING_VALUE]
        for assay in assays:
            names = bacteria or [MISSING_VALUE]
            for name in names:
                relation = assay.group("relation") or "="
                if relation in {"<=", ">="}:
                    relation = relation[0]
                for compound_id in compounds[:1]:
                    records.append(
                        BenzimidazoleRawRecord(
                            compound_id=compound_id,
                            target_type=assay.group("type"),
                            target_relation=relation,
                            target_value=assay.group("value").replace("–", "-").replace(" ", ""),
                            target_units=assay.group("unit") or MISSING_VALUE,
                            bacteria=name,
                            evidence=EvidenceProvenance(
                                source_file=chunk.source.source_file,
                                page=chunk.source.page,
                                section=chunk.source.section,
                                table_id=chunk.source.table_id,
                                row_id=chunk.row_id,
                                evidence_text=chunk.text,
                                extraction_method="benzimidazole.rule_extractor",
                                confidence=0.75 if chunk.row_id is not None else 0.6,
                            ),
                        )
                    )
    return records


def _extract_mic_table_rows(chunk: EvidenceChunk) -> list[BenzimidazoleRawRecord]:
    """Extract paired MIC columns from a text-layer table with explicit headers.

    The table's footnotes name the two organisms: column ``c`` is MTCC 3160
    and column ``d`` is MRSA.  Values are selected from the final four numeric
    columns of each visual row, which avoids treating IC50 standard deviations
    and scaffold substituent labels as MIC measurements.
    """
    header = TABLE_HEADER_RE.search(chunk.text)
    if not header:
        return []

    table_text = chunk.text[header.start():]
    table_end = re.search(r"^Novobiocin\b|^ND,\s*indicates", table_text, re.M)
    if table_end:
        table_text = table_text[:table_end.start()]

    records: list[BenzimidazoleRawRecord] = []
    for match in TABLE_ROW_RE.finditer(table_text):
        line = match.group(0)
        compound_id = match.group("id")
        values = list(NUMBER_RE.finditer(line))
        # Compound id plus at least four assay values is required.  The two
        # MIC cells precede biofilm and cytotoxicity columns.
        if len(values) < 5:
            continue
        mic_cells = values[-4:-2]
        if len(mic_cells) != 2:
            continue
        for organism, cell in zip(("MTCC 3160", "MRSA"), mic_cells, strict=True):
            records.append(
                BenzimidazoleRawRecord(
                    compound_id=compound_id,
                    target_type="MIC",
                    target_relation=cell.group("relation") or "=",
                    target_value=cell.group("value"),
                    target_units="µM",
                    bacteria=organism,
                    evidence=EvidenceProvenance(
                        source_file=chunk.source.source_file,
                        page=chunk.source.page,
                        section=chunk.source.section,
                        table_id=chunk.source.table_id or "table_like_text",
                        row_id=compound_id,
                        evidence_text=line,
                        extraction_method="benzimidazole.rule_extractor.table_like_text",
                        confidence=0.85,
                    ),
                )
            )
    return records
