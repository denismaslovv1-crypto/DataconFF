from __future__ import annotations

import re
from dataclasses import dataclass

from pdf_extraction.models import (
    ExtractedTable,
    ExtractedTextBlock,
    RawChemicalRecord,
    SourceProvenance,
)


COMPOUND_START_RE = re.compile(
    r"^(?P<label>(?:\d+[a-z]?(?:\([^)]+\))?|[A-Z]{1,4}-?\d+[a-z]?|[A-Za-z]+\d+[a-z]?))\s+(?P<values>.+)$"
)
VALUE_RE = re.compile(
    "^(?:[<>]?\\d[\\d,]*(?:\\.\\d+)?(?:(?:\\u00b1|\\+/-|\\()\\d[\\d,]*(?:\\.\\d+)?\\)?)?|"
    "nd|na|c|e|inactive|\\u2014|-|\"|[0-9:.\\/]+)$",
    re.I,
)
PROPERTY_HINT_RE = re.compile(
    r"(?:IC50|EC50|Ki|pIC50|pEC50|pKi|LogD|CLogP|Selectivity|binding|hERG|ORL1|NOP|MOP|DOP|KOP|MOR|DOR|KOR|CB1)",
    re.I,
)


@dataclass(frozen=True)
class ParsedLine:
    compound_label: str
    molecule_name: str | None
    values: list[str]
    raw_line: str


class ChemistryRecordExtractor:
    """Heuristic raw extractor for chemical assay rows.

    The extractor intentionally keeps raw rows and provenance. It is not a
    validator and does not attempt article-specific correction.
    """

    def extract(
        self,
        source_file: str,
        tables: list[ExtractedTable],
        text_blocks: list[ExtractedTextBlock],
    ) -> list[RawChemicalRecord]:
        records: list[RawChemicalRecord] = []
        records.extend(self._from_tables(source_file, tables))
        records.extend(self._from_text(source_file, text_blocks, offset=len(records)))
        return records

    def _from_tables(self, source_file: str, tables: list[ExtractedTable]) -> list[RawChemicalRecord]:
        records: list[RawChemicalRecord] = []
        source_key = self._source_key(source_file)
        for table in tables:
            expanded_rows = self._expand_rows(table.rows)
            header = self._header_text(expanded_rows)
            property_names = self._infer_property_names(header)
            for row_index, row in enumerate(expanded_rows, start=1):
                line = " ".join(cell for cell in row if cell).strip()
                parsed = self._parse_compound_line(line)
                if not parsed:
                    continue
                source = SourceProvenance(
                    source_file=source_file,
                    page=table.source.page,
                    section=header or None,
                    table_id=table.table_id,
                    row_index=row_index,
                    extraction_method="pdfplumber.table+chemical_row_heuristic",
                    confidence=0.65,
                )
                records.append(
                    RawChemicalRecord(
                        record_id=f"{source_key}_{table.table_id}_row{row_index}_raw",
                        record_type="raw_table_row",
                        compound_label=parsed.compound_label,
                        molecule_name=parsed.molecule_name,
                        raw_value=parsed.raw_line,
                        raw_row=row,
                        source=source,
                        confidence=0.65,
                    )
                )
                for value_index, value in enumerate(parsed.values, start=1):
                    property_name = self._property_name(property_names, value_index)
                    records.append(
                        RawChemicalRecord(
                            record_id=f"{source_key}_{table.table_id}_row{row_index}_v{value_index}",
                            record_type="table_property",
                            compound_label=parsed.compound_label,
                            molecule_name=parsed.molecule_name,
                            property_name=property_name,
                            property_value=value,
                            unit=self._unit_from_property(property_name),
                            raw_value=value,
                            raw_row=row,
                            source=source,
                            confidence=0.65,
                        )
                    )
        return records

    def _from_text(
        self,
        source_file: str,
        text_blocks: list[ExtractedTextBlock],
        offset: int = 0,
    ) -> list[RawChemicalRecord]:
        records: list[RawChemicalRecord] = []
        source_key = self._source_key(source_file)
        for block in text_blocks:
            recent_header = ""
            table_context_remaining = 0
            for line_index, raw_line in enumerate(block.text.splitlines(), start=1):
                line = " ".join(raw_line.split())
                if not line:
                    continue
                if "Table" in line:
                    recent_header = line[:400]
                    table_context_remaining = 50
                elif table_context_remaining > 0 and PROPERTY_HINT_RE.search(line):
                    recent_header = f"{recent_header} {line}"[:400]

                parsed = self._parse_compound_line(line)
                if not parsed or len(parsed.values) < 2:
                    table_context_remaining = max(0, table_context_remaining - 1)
                    continue

                in_table_context = table_context_remaining > 0 and PROPERTY_HINT_RE.search(recent_header)
                if not in_table_context:
                    table_context_remaining = max(0, table_context_remaining - 1)
                    continue

                property_names = self._infer_property_names(recent_header)
                if not property_names:
                    table_context_remaining = max(0, table_context_remaining - 1)
                    continue
                source = SourceProvenance(
                    source_file=source_file,
                    page=block.source.page,
                    section=recent_header or None,
                    row_index=line_index,
                    extraction_method="pdfplumber.text+chemical_row_heuristic",
                    confidence=0.45,
                )
                for value_index, value in enumerate(parsed.values, start=1):
                    property_name = self._property_name(property_names, value_index)
                    records.append(
                        RawChemicalRecord(
                            record_id=f"{source_key}_text_p{block.source.page}_l{line_index}_v{value_index}_{offset + len(records) + 1}",
                            record_type="text_property",
                            compound_label=parsed.compound_label,
                            molecule_name=parsed.molecule_name,
                            property_name=property_name,
                            property_value=value,
                            unit=self._unit_from_property(property_name),
                            raw_value=parsed.raw_line,
                            source=source,
                            confidence=0.45,
                        )
                    )
                table_context_remaining = max(0, table_context_remaining - 1)
        return records

    def _expand_rows(self, rows: list[list[str]]) -> list[list[str]]:
        expanded: list[list[str]] = []
        for row in rows:
            clean_row = [cell.strip() for cell in row if cell and cell.strip()]
            if len(clean_row) == 1 and "\n" in clean_row[0]:
                expanded.extend([[line.strip()] for line in clean_row[0].splitlines() if line.strip()])
            else:
                expanded.append(clean_row)
        return expanded

    def _header_text(self, rows: list[list[str]]) -> str:
        candidates = []
        include_next = False
        for row in rows[:6]:
            text = " ".join(row)
            if PROPERTY_HINT_RE.search(text) or include_next:
                candidates.append(text)
                include_next = bool(PROPERTY_HINT_RE.search(text))
            else:
                include_next = False
        return " ".join(candidates)[:500]

    def _parse_compound_line(self, line: str) -> ParsedLine | None:
        match = COMPOUND_START_RE.match(line)
        if not match:
            return None
        raw_label = match.group("label")
        values_text = match.group("values")
        compound_label = raw_label
        molecule_name = None
        paren = re.match(r"(?P<label>[^()]+)\((?P<name>[^)]+)\)", raw_label)
        if paren:
            compound_label = paren.group("label")
            molecule_name = paren.group("name")
        values = [token for token in values_text.split() if VALUE_RE.match(token)]
        if not values:
            return None
        return ParsedLine(
            compound_label=compound_label,
            molecule_name=molecule_name,
            values=values,
            raw_line=line,
        )

    def _infer_property_names(self, header: str) -> list[str]:
        if not header:
            return []
        names: list[str] = []
        compact = header.replace(" ", "")
        patterns = [
            ("NOPKi", "NOP_Ki"),
            ("MOPKi", "MOP_Ki"),
            ("DOPKi", "DOP_Ki"),
            ("KOPKi", "KOP_Ki"),
            ("ORL1binding", "ORL1_binding"),
            ("hERGbinding", "hERG_binding"),
            ("IC50", "IC50"),
            ("EC50", "EC50"),
            ("pIC50", "pIC50"),
            ("pEC50", "pEC50"),
            ("Ki", "Ki"),
            ("CLogP", "CLogP"),
            ("LogD", "LogD"),
            ("Selectivity", "selectivity"),
        ]
        for needle, name in patterns:
            if needle.lower() in compact.lower() or needle.lower() in header.lower():
                names.append(name)
        if any(token in header for token in ("DAMGO", "Naltindole", "U69", "j l d", "l d j")):
            names = ["mu_Ki", "delta_Ki", "kappa_Ki", "selectivity", "CLogP"]
        if "hERG" in header and "ORL1" in header:
            names = ["ORL1_IC50", "hERG_IC50", "LogD"]
        return names

    def _property_name(self, property_names: list[str], value_index: int) -> str:
        if value_index <= len(property_names):
            return property_names[value_index - 1]
        return f"table_value_{value_index}"

    def _unit_from_property(self, property_name: str | None) -> str | None:
        if not property_name:
            return None
        lowered = property_name.lower()
        if "ki" in lowered or "ic50" in lowered or "ec50" in lowered:
            return "nM"
        return None

    def _source_key(self, source_file: str) -> str:
        key = re.sub(r"[^A-Za-z0-9]+", "_", source_file.rsplit(".", 1)[0]).strip("_")
        return key[:80] or "pdf"
