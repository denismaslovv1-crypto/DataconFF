from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from pdf_extraction.models import ExtractedTable, ParsedPdfDocument


MISSING_VALUE = "NOT_DETECTED"

SYNERGY_COLUMNS = (
    "sn",
    "NP",
    "bacteria",
    "strain",
    "NP_synthesis",
    "drug",
    "drug_dose_µg_disk",
    "NP_concentration_µg_ml",
    "NP_size_min_nm",
    "NP_size_max_nm",
    "NP_size_avg_nm",
    "shape",
    "method",
    "ZOI_drug_mm_or_MIC _µg_ml",
    "error_ZOI_drug_mm_or_MIC_µg_ml",
    "ZOI_NP_mm_or_MIC_np_µg_ml",
    "error_ZOI_NP_mm_or_MIC_np_µg_ml",
    "ZOI_drug_NP_mm_or_MIC_drug_NP_µg_ml",
    "error_ZOI_drug_NP_mm_or_MIC_drug_NP_µg_ml",
    "fold_increase_in_antibacterial_activity",
    "zeta_potential_mV",
    "MDR",
    "FIC",
    "effect",
    "reference",
    "doi",
    "article_list",
    "time_hr",
    "coating_with_antimicrobial_peptide_polymers",
    "combined_MIC",
    "peptide_MIC",
    "viability_%",
    "viability_error",
    "journal_name",
    "publisher",
    "year",
    "title",
    "journal_is_oa",
    "is_oa",
    "oa_status",
    "pdf",
    "access",
)

RISKY_BLANK_COLUMNS = {
    "strain",
    "NP_synthesis",
    "error_ZOI_drug_mm_or_MIC_µg_ml",
    "error_ZOI_NP_mm_or_MIC_np_µg_ml",
    "error_ZOI_drug_NP_mm_or_MIC_drug_NP_µg_ml",
    "fold_increase_in_antibacterial_activity",
    "zeta_potential_mV",
    "MDR",
    "effect",
    "reference",
    "article_list",
    "coating_with_antimicrobial_peptide_polymers",
    "combined_MIC",
    "peptide_MIC",
    "viability_error",
    "journal_name",
    "publisher",
    "journal_is_oa",
    "is_oa",
    "oa_status",
    "access",
}

NP_PATTERNS = (
    (r"\bAgNPs?\b|\bsilver nanoparticles?\b|\bAg nanoparticles?\b", "Ag"),
    (r"\bAuNPs?\b|\bgold nanoparticles?\b|\bAu nanoparticles?\b", "Au"),
    (r"\bZnO\b|\bzinc oxide nanoparticles?\b", "ZnO"),
    (r"\bTiO2\b|\btitanium dioxide nanoparticles?\b", "TiO2"),
    (r"\bCuO\b|\bcopper oxide nanoparticles?\b", "CuO"),
    (r"\bFe3O4\b|\biron oxide nanoparticles?\b|\bmagnetite nanoparticles?\b", "Fe3O4"),
    (r"\bFe2O3\b|\bhematite nanoparticles?\b", "Fe2O3"),
    (r"\bchitosan\b", "Chitosan"),
    (r"\bgraphene oxide\b|\breduced graphene oxide\b|\brGO\b", "graphene oxide"),
    (r"\bnanocomposites?\b", "nanocomposite"),
    (r"\bnanoparticles?\b|\bNPs?\b", "nanoparticle"),
)

BACTERIA_PATTERNS = (
    (r"\bE\.?\s*coli\b|\bEscherichia coli\b", "Escherichia coli"),
    (r"\bS\.?\s*aureus\b|\bStaphylococcus aureus\b", "Staphylococcus aureus"),
    (r"\bP\.?\s*aeruginosa\b|\bPseudomonas aeruginosa\b", "Pseudomonas aeruginosa"),
    (r"\bB\.?\s*subtilis\b|\bBacillus subtilis\b", "Bacillus subtilis"),
    (r"\bK\.?\s*pneumoniae\b|\bKlebsiella pneumoniae\b", "Klebsiella pneumoniae"),
    (r"\bA\.?\s*baumannii\b|\bAcinetobacter baumannii\b", "Acinetobacter baumannii"),
    (r"\bE\.?\s*faecalis\b|\bEnterococcus faecalis\b", "Enterococcus faecalis"),
    (r"\bB\.?\s*cenocepacia\b|\bBurkholderia cenocepacia\b", "Burkholderia cenocepacia"),
    (r"\bBurkholderia pseudomallei\b|\bB\.?\s*pseudomallei\b", "Burkholderia pseudomallei"),
    (r"\bCandida albicans\b|\bC\.?\s*albicans\b", "Candida albicans"),
)

DRUG_PATTERNS = (
    "amikacin",
    "amoxicillin",
    "ampicillin",
    "azithromycin",
    "aztreonam",
    "bacitracin",
    "cefotaxime",
    "ceftazidime",
    "ceftriaxone",
    "cefazolin",
    "cefepime",
    "cefoxitin",
    "chloramphenicol",
    "ciprofloxacin",
    "colistin",
    "doxycycline",
    "erythromycin",
    "gatifloxacin",
    "gentamicin",
    "gentamycin",
    "imipenem",
    "kanamycin",
    "levofloxacin",
    "meropenem",
    "moxifloxacin",
    "neomycin",
    "piperacillin",
    "rifampicin",
    "streptomycin",
    "tetracycline",
    "tobramycin",
    "vancomycin",
)

SHAPE_PATTERNS = (
    (r"\bspherical\b|\bsphere\b", "spherical"),
    (r"\brod[- ]?shaped\b|\brods?\b", "rod"),
    (r"\bcubic\b|\bcubes?\b|\bnanocubes?\b", "cubic"),
    (r"\btriangular\b", "triangular"),
    (r"\birregular\b", "irregular"),
)


@dataclass(frozen=True)
class SynergyEvidence:
    source_file: str
    page: int | None
    table_id: str | None
    row_id: str | None
    evidence_text: str
    extraction_method: str
    confidence: float


@dataclass(frozen=True)
class SynergyRecord:
    row: dict[str, str]
    evidence: SynergyEvidence


def extract_synergy_records(document: ParsedPdfDocument, pdf_path: Path) -> list[SynergyRecord]:
    """Extract a small source-backed Synergy MVP from parser text/tables."""

    metadata = _article_metadata(document, pdf_path)
    records: list[SynergyRecord] = []
    seen: set[tuple[str, ...]] = set()

    for table in document.tables:
        for record in _records_from_table(table, document.source_file, metadata):
            key = _dedup_key(record)
            if key not in seen:
                seen.add(key)
                records.append(record)

    for block in document.text_blocks:
        page_text = _clean_space(block.text)
        if not page_text:
            continue
        page_defaults = _context_defaults(page_text)
        for index, snippet in enumerate(_candidate_snippets(page_text), start=1):
            for record in _records_from_snippet(
                snippet,
                document.source_file,
                block.source.page,
                f"text-{index}",
                metadata,
                page_defaults,
            ):
                key = _dedup_key(record)
                if key not in seen:
                    seen.add(key)
                    records.append(record)

    return records


def chemx_row(record: SynergyRecord, sn: int) -> dict[str, str]:
    row = {column: record.row.get(column, "") for column in SYNERGY_COLUMNS}
    row["sn"] = str(sn)
    return row


def review_row(record: SynergyRecord, row: dict[str, str], evidence_id: str) -> dict[str, str]:
    return {
        "pdf": row.get("pdf", ""),
        "sn": row.get("sn", ""),
        "NP": row.get("NP", ""),
        "bacteria": row.get("bacteria", ""),
        "drug": row.get("drug", ""),
        "method": row.get("method", ""),
        "value_drug": row.get("ZOI_drug_mm_or_MIC _µg_ml", ""),
        "value_np": row.get("ZOI_NP_mm_or_MIC_np_µg_ml", ""),
        "value_combined": row.get("ZOI_drug_NP_mm_or_MIC_drug_NP_µg_ml", ""),
        "FIC": row.get("FIC", ""),
        "page": "" if record.evidence.page is None else str(record.evidence.page),
        "table_id": record.evidence.table_id or "",
        "row_id": record.evidence.row_id or "",
        "evidence_id": evidence_id,
        "source_text": _truncate(record.evidence.evidence_text, 1200),
        "extractor": record.evidence.extraction_method,
        "confidence": f"{record.evidence.confidence:.2f}",
    }


def _records_from_table(
    table: ExtractedTable,
    source_file: str,
    metadata: dict[str, str],
) -> Iterable[SynergyRecord]:
    table_text = "\n".join(" | ".join(row) for row in table.rows)
    table_defaults = _context_defaults(table_text)
    headers = _find_header(table.rows)
    for row_index, cells in enumerate(table.rows, start=1):
        row_text = " | ".join(cells)
        if not _has_signal(row_text):
            continue
        values = _values_from_cells(cells, headers)
        yield from _records_from_snippet(
            row_text,
            source_file,
            table.source.page,
            str(row_index),
            metadata,
            table_defaults | values,
            table_id=table.table_id,
            method_name="synergy.table_rules",
            confidence=0.72,
        )


def _records_from_snippet(
    snippet: str,
    source_file: str,
    page: int | None,
    row_id: str,
    metadata: dict[str, str],
    defaults: dict[str, str],
    table_id: str | None = None,
    method_name: str = "synergy.text_rules",
    confidence: float = 0.58,
) -> Iterable[SynergyRecord]:
    fields = _context_defaults(snippet)
    fields = defaults | fields
    if not _record_is_supported(fields):
        return
    if method_name == "synergy.text_rules" and not _has_activity_measure(fields):
        return

    bacteria = _first_or_missing(fields.get("bacteria"))
    drugs = _split_multi(fields.get("drug")) or [MISSING_VALUE]
    for drug in drugs[:4]:
        row = _empty_row()
        row.update(metadata)
        row.update(
            {
                "NP": _first_or_missing(fields.get("NP")),
                "bacteria": bacteria,
                "drug": drug,
                "method": fields.get("method", MISSING_VALUE),
                "drug_dose_µg_disk": fields.get("drug_dose_µg_disk", ""),
                "NP_concentration_µg_ml": fields.get("NP_concentration_µg_ml", ""),
                "NP_size_min_nm": fields.get("NP_size_min_nm", ""),
                "NP_size_max_nm": fields.get("NP_size_max_nm", ""),
                "NP_size_avg_nm": fields.get("NP_size_avg_nm", ""),
                "shape": fields.get("shape", ""),
                "ZOI_drug_mm_or_MIC _µg_ml": fields.get("ZOI_drug_mm_or_MIC _µg_ml", ""),
                "ZOI_NP_mm_or_MIC_np_µg_ml": fields.get("ZOI_NP_mm_or_MIC_np_µg_ml", ""),
                "ZOI_drug_NP_mm_or_MIC_drug_NP_µg_ml": fields.get(
                    "ZOI_drug_NP_mm_or_MIC_drug_NP_µg_ml", ""
                ),
                "FIC": fields.get("FIC", ""),
                "time_hr": fields.get("time_hr", ""),
                "viability_%": fields.get("viability_%", ""),
            }
        )
        if _has_extracted_payload(row):
            yield SynergyRecord(
                row=row,
                evidence=SynergyEvidence(
                    source_file=source_file,
                    page=page,
                    table_id=table_id,
                    row_id=row_id,
                    evidence_text=snippet,
                    extraction_method=method_name,
                    confidence=confidence,
                ),
            )


def _article_metadata(document: ParsedPdfDocument, pdf_path: Path) -> dict[str, str]:
    full_text = "\n".join(block.text for block in document.text_blocks[:2])
    doi = _first_match(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", full_text, flags=re.I)
    year = _first_match(r"\b(19|20)\d{2}\b", full_text)
    title = ""
    for line in full_text.splitlines():
        cleaned = _clean_space(line)
        if 20 <= len(cleaned) <= 220 and not cleaned.lower().startswith(("contents", "doi ", "received")):
            if any(term in cleaned.lower() for term in ("nanoparticle", "antibacterial", "synerg")):
                title = cleaned
                break
    return {
        "doi": doi.lower() if doi else "",
        "year": year or "",
        "title": title,
        "pdf": pdf_path.name,
    }


def _context_defaults(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    nps = _detect_patterns(text, NP_PATTERNS)
    if nps:
        fields["NP"] = nps[0]
    bacteria = _detect_patterns(text, BACTERIA_PATTERNS)
    if bacteria:
        fields["bacteria"] = bacteria[0]
    drugs = _detect_drugs(text)
    if drugs:
        fields["drug"] = ";".join(drugs)
    method = _detect_method(text)
    if method:
        fields["method"] = method
    shape = _detect_patterns(text, SHAPE_PATTERNS)
    if shape:
        fields["shape"] = shape[0]
    fields.update(_detect_sizes(text))
    fields.update(_detect_concentrations(text))
    fields.update(_detect_activity_values(text, method))
    return fields


def _candidate_snippets(page_text: str) -> list[str]:
    rough = re.split(r"(?<=[.;])\s+|\n+", page_text)
    snippets: list[str] = []
    carry = ""
    for piece in rough:
        piece = _clean_space(piece)
        if not piece:
            continue
        combined = _clean_space(f"{carry} {piece}") if carry else piece
        if _has_signal(combined):
            snippets.append(combined)
        carry = piece[-350:]
    return snippets[:80]


def _has_signal(text: str) -> bool:
    lowered = text.lower()
    return any(
        token in lowered
        for token in (
            "mic",
            "mbec",
            "fic",
            "zone",
            "inhibition",
            "antibacterial",
            "synerg",
            "viability",
            "µg",
            "ug",
            "mg/ml",
            "mm",
            "nm",
        )
    )


def _record_is_supported(fields: dict[str, str]) -> bool:
    has_np = bool(fields.get("NP"))
    has_link = any(fields.get(key) for key in ("bacteria", "drug", "method"))
    has_measure = any(
        fields.get(key)
        for key in (
            "ZOI_drug_mm_or_MIC _µg_ml",
            "ZOI_NP_mm_or_MIC_np_µg_ml",
            "ZOI_drug_NP_mm_or_MIC_drug_NP_µg_ml",
            "FIC",
            "NP_concentration_µg_ml",
            "drug_dose_µg_disk",
        )
    )
    return has_np and has_link and (has_measure or bool(fields.get("bacteria")))


def _has_activity_measure(fields: dict[str, str]) -> bool:
    return any(
        fields.get(key)
        for key in (
            "ZOI_drug_mm_or_MIC _µg_ml",
            "ZOI_NP_mm_or_MIC_np_µg_ml",
            "ZOI_drug_NP_mm_or_MIC_drug_NP_µg_ml",
            "FIC",
            "viability_%",
        )
    )


def _has_extracted_payload(row: dict[str, str]) -> bool:
    return row.get("NP") not in ("", MISSING_VALUE) and any(
        row.get(key) not in ("", MISSING_VALUE)
        for key in ("bacteria", "drug", "method", "ZOI_drug_mm_or_MIC _µg_ml", "FIC")
    )


def _empty_row() -> dict[str, str]:
    row = {column: "" for column in SYNERGY_COLUMNS}
    for column in RISKY_BLANK_COLUMNS:
        row[column] = ""
    for column in ("NP", "bacteria", "drug", "method"):
        row[column] = MISSING_VALUE
    return row


def _detect_patterns(text: str, patterns: Iterable[tuple[str, str]]) -> list[str]:
    found: list[str] = []
    for pattern, value in patterns:
        if re.search(pattern, text, flags=re.I) and value not in found:
            found.append(value)
    return found


def _detect_drugs(text: str) -> list[str]:
    found: list[str] = []
    for drug in DRUG_PATTERNS:
        if re.search(rf"\b{re.escape(drug)}\b", text, flags=re.I):
            label = "Gentamicin" if drug == "gentamycin" else drug.capitalize()
            if label not in found:
                found.append(label)
    return found


def _detect_method(text: str) -> str:
    lowered = text.lower()
    if re.search(r"\bfici?\b|fractional inhibitory", lowered):
        return "FIC"
    if re.search(r"\bmbec\b", lowered):
        return "MBEC"
    if re.search(r"\bmic\b|minimum inhibitory concentration", lowered):
        return "MIC"
    if "viability" in lowered:
        return "viability (%)"
    if "zone" in lowered or "disc diffusion" in lowered or "disk diffusion" in lowered:
        return "disc_diffusion"
    if "inhibition" in lowered:
        return "ZOI"
    return ""


def _detect_sizes(text: str) -> dict[str, str]:
    values = [
        _format_number(match.group("value"))
        for match in re.finditer(
            r"(?P<value>\d+(?:\.\d+)?)\s*(?:-|to|–)?\s*(?:\d+(?:\.\d+)?\s*)?nm\b",
            text,
            flags=re.I,
        )
    ]
    if not values:
        return {}
    result = {"NP_size_avg_nm": values[0]}
    range_match = re.search(
        r"(?P<min>\d+(?:\.\d+)?)\s*(?:-|to|–)\s*(?P<max>\d+(?:\.\d+)?)\s*nm\b",
        text,
        flags=re.I,
    )
    if range_match:
        result["NP_size_min_nm"] = _format_number(range_match.group("min"))
        result["NP_size_max_nm"] = _format_number(range_match.group("max"))
    return result


def _detect_concentrations(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    disk = re.search(
        r"(?P<value>\d+(?:\.\d+)?)\s*(?:µg|ug|μg)\s*/?\s*(?:disc|disk)",
        text,
        flags=re.I,
    )
    if disk:
        fields["drug_dose_µg_disk"] = _format_number(disk.group("value"))
    np_conc = re.search(
        r"(?P<value>\d+(?:\.\d+)?)\s*(?:µg|ug|μg)\s*/?\s*(?:mL|ml)\b",
        text,
        flags=re.I,
    )
    if np_conc:
        fields["NP_concentration_µg_ml"] = _format_number(np_conc.group("value"))
    time = re.search(r"(?P<value>\d+(?:\.\d+)?)\s*h(?:ours?|r)?\b", text, flags=re.I)
    if time:
        fields["time_hr"] = _format_number(time.group("value"))
    return fields


def _detect_activity_values(text: str, method: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    if method == "FIC":
        fic = re.search(r"\bFICI?\D{0,12}(?P<value>\d+(?:\.\d+)?)\b", text, flags=re.I)
        if fic:
            fields["FIC"] = _format_number(fic.group("value"))
    if method in {"disc_diffusion", "ZOI"} or re.search(r"\bzone\b", text, flags=re.I):
        mm = re.search(r"(?P<value>\d+(?:\.\d+)?)\s*mm\b", text, flags=re.I)
        if mm:
            key = (
                "ZOI_drug_NP_mm_or_MIC_drug_NP_µg_ml"
                if re.search(r"combin|synerg|\+", text, flags=re.I)
                else "ZOI_NP_mm_or_MIC_np_µg_ml"
            )
            fields[key] = _format_number(mm.group("value"))
    if method in {"MIC", "MBEC"}:
        mic = re.search(
            r"(?:MIC|MBEC|concentration)\D{0,30}(?P<value>\d+(?:\.\d+)?)\s*(?:µg|ug|μg|mg)\s*/?\s*(?:mL|ml)\b",
            text,
            flags=re.I,
        )
        if mic:
            key = (
                "ZOI_drug_NP_mm_or_MIC_drug_NP_µg_ml"
                if re.search(r"combin|synerg|\+", text, flags=re.I)
                else "ZOI_NP_mm_or_MIC_np_µg_ml"
            )
            fields[key] = _format_number(mic.group("value"))
    if method == "viability (%)":
        viability = re.search(r"(?P<value>\d+(?:\.\d+)?)\s*%", text)
        if viability:
            fields["viability_%"] = _format_number(viability.group("value"))
    return fields


def _find_header(rows: list[list[str]]) -> list[str]:
    for row in rows[:3]:
        joined = " ".join(row).lower()
        if any(token in joined for token in ("mic", "fic", "drug", "bacteria", "strain", "np", "ag")):
            return row
    return rows[0] if rows else []


def _values_from_cells(cells: list[str], headers: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for header, cell in zip(headers, cells, strict=False):
        h = header.lower()
        value = _first_numeric(cell)
        if not value:
            continue
        if "fici" in h or re.fullmatch(r"\s*fic\s*", h):
            fields["FIC"] = value
            fields["method"] = "FIC"
        elif "mic" in h or "mbec" in h:
            fields["ZOI_drug_NP_mm_or_MIC_drug_NP_µg_ml"] = value
            fields["method"] = "MIC" if "mic" in h else "MBEC"
        elif "zone" in h or "zoi" in h or "inhibition" in h:
            fields["ZOI_drug_NP_mm_or_MIC_drug_NP_µg_ml"] = value
            fields["method"] = "disc_diffusion"
        elif "ag" in h or "np" in h:
            fields["NP_concentration_µg_ml"] = value
    return fields


def _split_multi(value: str | None) -> list[str]:
    if not value:
        return []
    return [piece for piece in value.split(";") if piece]


def _first_or_missing(value: str | None) -> str:
    if not value:
        return MISSING_VALUE
    return value.split(";")[0]


def _first_match(pattern: str, text: str, flags: int = 0) -> str:
    match = re.search(pattern, text, flags=flags)
    return match.group(0).strip(".,;:") if match else ""


def _first_numeric(text: str) -> str:
    match = re.search(r"\d+(?:\.\d+)?", text)
    return _format_number(match.group(0)) if match else ""


def _format_number(value: str | None) -> str:
    if value is None:
        return ""
    cleaned = value.replace(",", ".").strip()
    try:
        number = float(cleaned)
    except ValueError:
        return cleaned
    return f"{number:.6g}"


def _dedup_key(record: SynergyRecord) -> tuple[str, ...]:
    row = record.row
    return (
        row.get("pdf", ""),
        row.get("NP", ""),
        row.get("bacteria", ""),
        row.get("drug", ""),
        row.get("method", ""),
        row.get("NP_concentration_µg_ml", ""),
        row.get("ZOI_drug_mm_or_MIC _µg_ml", ""),
        row.get("ZOI_NP_mm_or_MIC_np_µg_ml", ""),
        row.get("ZOI_drug_NP_mm_or_MIC_drug_NP_µg_ml", ""),
        row.get("FIC", ""),
        record.evidence.page or 0,
        record.evidence.row_id or "",
    )


def _clean_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _truncate(value: str, limit: int) -> str:
    cleaned = _clean_space(value)
    return cleaned if len(cleaned) <= limit else f"{cleaned[: limit - 3]}..."
