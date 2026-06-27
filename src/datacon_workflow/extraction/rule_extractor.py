from __future__ import annotations

import re

from datacon_workflow.domains.benzimidazoles import BenzimidazoleRawRecord, EvidenceProvenance, MISSING_VALUE
from datacon_workflow.domains.benzimidazole_units import extract_target_unit_from_evidence
from datacon_workflow.extraction.evidence_builder import EvidenceChunk


ASSAY_RE = re.compile(
    r"\b(?P<type>p?MIC)\b[^<>=\d]{0,40}(?P<relation><=|>=|<|>|=)?\s*(?P<value>\d+(?:\.\d+)?(?:\s*[-–]\s*\d+(?:\.\d+)?)?)\s*(?P<unit>µg/mL|μg/mL|ug/mL|mcg/mL|microg/mL|mg/L|mmol/L|mmol/l)?",
    re.I,
)
COMPOUND_RE = re.compile(r"\b(?:compound\s+)?(?P<id>\d+[a-z]{0,3}|[A-Z]{1,4}-\d{1,3}|[A-Z]\d{1,3})\b", re.I)
BACTERIA_RE = re.compile(r"(?P<name>S\.\s*aureus|Staph\.\s*aureus|Staphylococcus\s+aureus|E\.\s*coli|Escherichia\s+coli)", re.I)
TABLE_HEADER_RE = re.compile(r"\bMIC\s*\([^)]*\)\s*[cd].*?MRSA\s*MIC", re.I)
TABLE_ROW_RE = re.compile(r"^\s*(?P<id>\d{1,3})\s+.+$", re.M)
NUMBER_RE = re.compile(r"(?<![A-Za-z])(?P<relation>[<>])?\s*(?P<value>\d+(?:\.\d+)?)")
ANTIMICROBIAL_ROW_RE = re.compile(r"^\s*\d+\s+(?P<id>[1-4][a-z])\s+(?P<cells>.+)$", re.M | re.I)
ANTIMICROBIAL_COLUMNS = (
    ("Escherichia coli ATCC 25922", 0),
    ("MSSA, Methicillin-susceptible strains of Staphylococcus aureus ATCC 29213", 3),
    ("MRSA, Methicillin-resistant strains of Staphylococcus aureus ATCC 43300", 4),
)
TARGET_ANTIBACTERIAL_COLUMNS = {
    "S.aureus": "S. aureus",
    "Staphylococcusaureus": "Staphylococcus aureus",
    "E.coli": "E. coli",
    "Escherichiacoli": "Escherichia coli",
}
ABBREVIATED_ORGANISM_COLUMNS = {
    "Sa": "S. aureus",
    "Ec": "E. coli",
}


def extract_records(chunks: list[EvidenceChunk]) -> list[BenzimidazoleRawRecord]:
    records: list[BenzimidazoleRawRecord] = []
    table_sources: set[tuple[str, int | None]] = set()
    for chunk in chunks:
        table_records = (
            _extract_bk_antibacterial_table_rows(chunk)
            or _extract_abbreviated_antimicrobial_table_rows(chunk)
            or _extract_mic_table_rows(chunk)
            or _extract_antimicrobial_table_rows(chunk)
        )
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
            target_value = assay.group("value").replace("–", "-").replace(" ", "")
            target_units = assay.group("unit") or extract_target_unit_from_evidence(chunk.text, target_value)
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
                            target_value=target_value,
                            target_units=target_units,
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


def _extract_bk_antibacterial_table_rows(chunk: EvidenceChunk) -> list[BenzimidazoleRawRecord]:
    """Extract table-like antibacterial MIC rows with IDs such as BK-1.

    Some text-layer tables carry the unit only in the title/header and include
    non-target antibacterial, antifungal, and antioxidant columns. This parser
    keeps only supported ChemX bacteria columns from the same evidence chunk.
    """
    if "MIC" not in chunk.text or not re.search(r"\b[A-Z]{1,4}-\d{1,3}\b", chunk.text):
        return []
    unit = extract_target_unit_from_evidence(chunk.text)
    if unit == MISSING_VALUE:
        return []

    lines = [line.strip() for line in chunk.text.splitlines() if line.strip()]
    header_tokens: list[str] = []
    records: list[BenzimidazoleRawRecord] = []
    target_indexes: dict[int, str] = {}
    for line in lines:
        if re.search(r"\bCompounds?\b", line, re.I) and re.search(r"\b(?:S\.?aureus|E\.?coli)\b", line, re.I):
            header_tokens = re.split(r"\s+", line)
            target_indexes = _target_antibacterial_indexes(header_tokens)
            continue
        row = re.match(r"^(?P<id>[A-Z]{1,4}-\d{1,3})\s+(?P<cells>.+)$", line, re.I)
        if row is None or not target_indexes:
            continue
        cells = re.split(r"\s+", row.group("cells").strip())
        for index, organism in target_indexes.items():
            value_index = index - 1
            if value_index < 0 or value_index >= len(cells):
                continue
            numeric = re.fullmatch(r"(?P<relation>[<>])?(?P<value>\d+(?:\.\d+)?)", cells[value_index])
            if numeric is None:
                continue
            evidence_text = _table_context_evidence(chunk.text, header_tokens, line)
            records.append(
                BenzimidazoleRawRecord(
                    compound_id=row.group("id"),
                    target_type="MIC",
                    target_relation=numeric.group("relation") or "=",
                    target_value=numeric.group("value"),
                    target_units=unit,
                    bacteria=organism,
                    evidence=EvidenceProvenance(
                        source_file=chunk.source.source_file,
                        page=chunk.source.page,
                        section=chunk.source.section,
                        table_id=chunk.source.table_id or "table_like_text",
                        row_id=row.group("id"),
                        evidence_text=evidence_text,
                        extraction_method="benzimidazole.rule_extractor.target_antibacterial_table",
                        confidence=0.85,
                    ),
                )
            )
    return records


def _target_antibacterial_indexes(header_tokens: list[str]) -> dict[int, str]:
    indexes: dict[int, str] = {}
    for index, token in enumerate(header_tokens):
        normalized = re.sub(r"\s+", "", token)
        organism = TARGET_ANTIBACTERIAL_COLUMNS.get(normalized)
        if organism:
            indexes[index] = organism
    return indexes


def _table_context_evidence(table_text: str, header_tokens: list[str], row_line: str) -> str:
    title = ""
    for line in table_text.splitlines():
        if "MIC" in line:
            title = line.strip()
            break
    header = " ".join(header_tokens)
    return "\n".join(part for part in (title, header, row_line) if part)


def _extract_abbreviated_antimicrobial_table_rows(chunk: EvidenceChunk) -> list[BenzimidazoleRawRecord]:
    """Extract MIC rows from compact antimicrobial tables with organism codes.

    Some publisher text layers emit table headings as a grouped line followed
    by abbreviations such as ``Bc Sa Pa Ec Ab Ca``.  This keeps only the
    ChemX-supported antibacterial columns and ignores standards/fungal columns.
    """
    if not re.search(r"\bCompd\.?\s*no\b", chunk.text, re.I) or "MIC" not in chunk.text:
        return []
    unit = extract_target_unit_from_evidence(chunk.text)
    if unit == MISSING_VALUE:
        return []

    lines = [line.strip() for line in chunk.text.splitlines() if line.strip()]
    records: list[BenzimidazoleRawRecord] = []
    header_tokens: list[str] = []
    target_indexes: dict[int, str] = {}
    for line in lines:
        tokens = re.split(r"\s+", line)
        if {"Sa", "Ec"}.issubset(set(tokens)):
            header_tokens = tokens
            target_indexes = {
                index: organism
                for index, token in enumerate(header_tokens)
                if (organism := ABBREVIATED_ORGANISM_COLUMNS.get(token))
            }
            continue

        row = re.match(r"^(?P<id>\d+[a-z])\s+(?P<cells>(?:[<>]?\d+(?:\.\d+)?|[–-])(?:\s+(?:[<>]?\d+(?:\.\d+)?|[–-])){3,})$", line, re.I)
        if row is None or not target_indexes:
            continue
        cells = re.split(r"\s+", row.group("cells").strip())
        for index, organism in target_indexes.items():
            if index >= len(cells):
                continue
            numeric = re.fullmatch(r"(?P<relation>[<>])?(?P<value>\d+(?:\.\d+)?)", cells[index])
            if numeric is None:
                continue
            evidence_text = _table_context_evidence(chunk.text, header_tokens, line)
            records.append(
                BenzimidazoleRawRecord(
                    compound_id=row.group("id"),
                    target_type="MIC",
                    target_relation=numeric.group("relation") or "=",
                    target_value=numeric.group("value"),
                    target_units=unit,
                    bacteria=organism,
                    evidence=EvidenceProvenance(
                        source_file=chunk.source.source_file,
                        page=chunk.source.page,
                        section=chunk.source.section,
                        table_id=chunk.source.table_id or "table_like_text",
                        row_id=row.group("id"),
                        evidence_text=evidence_text,
                        extraction_method="benzimidazole.rule_extractor.abbreviated_antimicrobial_table",
                        confidence=0.85,
                    ),
                )
            )
    return records


def _extract_antimicrobial_table_rows(chunk: EvidenceChunk) -> list[BenzimidazoleRawRecord]:
    """Extract EC/MSSA/MRSA columns from a clearly labelled MIC table.

    Some RSC PDFs expose a landscape table with glyphs in reverse order in the
    text layer.  Reversing *each line* is safe only when both reversed header
    labels are present; the normal table layout is otherwise left untouched.
    """
    table_text = chunk.text
    if "edoC" in table_text and "yrtnE" in table_text:
        table_text = "\n".join(line[::-1] for line in table_text.splitlines())
    if not all(label in table_text for label in ("Antibacterial", "MSSA", "MRSA", "Entry", "Code")):
        return []

    records: list[BenzimidazoleRawRecord] = []
    for match in ANTIMICROBIAL_ROW_RE.finditer(table_text):
        cells = re.split(r"\s+", match.group("cells").strip())
        # The first five assay cells have the header order EC, PA, SF, MSSA,
        # MRSA. Remaining cells belong to antifungal/anticancer columns.
        if len(cells) < 5:
            continue
        for organism, index in ANTIMICROBIAL_COLUMNS:
            cell = cells[index]
            numeric = re.fullmatch(r"(?P<relation>[<>])?(?P<value>\d+(?:\.\d+)?)", cell)
            if numeric is None:
                continue
            records.append(
                BenzimidazoleRawRecord(
                    compound_id=match.group("id"),
                    target_type="MIC",
                    target_relation=numeric.group("relation") or "=",
                    target_value=numeric.group("value"),
                    target_units="mg/mL",
                    bacteria=organism,
                    evidence=EvidenceProvenance(
                        source_file=chunk.source.source_file,
                        page=chunk.source.page,
                        section=chunk.source.section,
                        table_id=chunk.source.table_id or "table_like_text",
                        row_id=match.group("id"),
                        evidence_text=match.group(0),
                        extraction_method="benzimidazole.rule_extractor.antimicrobial_table",
                        confidence=0.85,
                    ),
                )
            )
    if records:
        return records

    # Landscape tables can be emitted column-by-column: twelve assay cells,
    # then the compound code and entry number. Reassemble only this explicit
    # layout, keeping the same three antibacterial columns as above.
    lines = [line.strip() for line in table_text.splitlines()]
    try:
        data_start = lines.index("Entry") + 1
    except ValueError:
        return []
    for code_index in range(data_start + 12, len(lines)):
        compound_id = lines[code_index]
        if not re.fullmatch(r"[1-4][a-z]", compound_id, re.I):
            continue
        cells = lines[code_index - 12:code_index]
        for organism, cell_index in (
            ("Escherichia coli ATCC 25922", 11),
            ("MSSA, Methicillin-susceptible strains of Staphylococcus aureus ATCC 29213", 8),
            ("MRSA, Methicillin-resistant strains of Staphylococcus aureus ATCC 43300", 7),
        ):
            numeric = re.fullmatch(r"(?P<relation>[<>])?(?P<value>\d+(?:\.\d+)?)", cells[cell_index])
            if numeric is None:
                continue
            records.append(
                BenzimidazoleRawRecord(
                    compound_id=compound_id,
                    target_type="MIC",
                    target_relation=numeric.group("relation") or "=",
                    target_value=numeric.group("value"),
                    target_units="mg/mL",
                    bacteria=organism,
                    evidence=EvidenceProvenance(
                        source_file=chunk.source.source_file,
                        page=chunk.source.page,
                        section=chunk.source.section,
                        table_id=chunk.source.table_id or "table_like_text",
                        row_id=compound_id,
                        evidence_text="\n".join(lines[code_index - 12:code_index + 2]),
                        extraction_method="benzimidazole.rule_extractor.antimicrobial_table_vertical",
                        confidence=0.8,
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
