from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from pdf_extraction.models import ParsedPdfDocument, RawChemicalRecord
from pdf_extraction.structure_quality import is_generic_structure


RECORD_COLUMNS = [
    "record_id",
    "record_type",
    "source_file",
    "page",
    "section",
    "table_id",
    "figure_id",
    "row_index",
    "extraction_method",
    "confidence",
    "compound_label",
    "structure_id",
    "image_id",
    "caption",
    "crop_image_path",
    "bbox_points",
    "bbox_pixels",
    "is_generic_structure",
    "generic_structure_reason",
    "structure_resolution_status",
    "needs_structure_image_mapping",
    "molecule_name",
    "formula",
    "molecular_weight",
    "SMILES",
    "canonical_SMILES",
    "isomeric_SMILES",
    "InChI",
    "InChIKey",
    "CAS",
    "property_name",
    "property_value",
    "unit",
    "raw_value",
    "validation_status",
]

LABEL_COLUMNS = [
    "source_file",
    "compound_label",
    "molecule_name",
    "record_count",
    "pages",
    "property_names",
    "structure_resolution_status",
    "needs_structure_image_mapping",
]


def write_document_json(document: ParsedPdfDocument, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(document.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_records_csv(records: Iterable[RawChemicalRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=RECORD_COLUMNS)
        writer.writeheader()
        for record in records:
            writer.writerow(_record_row(record))


def write_compound_labels_csv(records: Iterable[RawChemicalRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    grouped: dict[tuple[str, str], list[RawChemicalRecord]] = {}
    for record in records:
        if not record.compound_label:
            continue
        key = (record.source.source_file, record.compound_label)
        grouped.setdefault(key, []).append(record)

    with output_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=LABEL_COLUMNS)
        writer.writeheader()
        for (source_file, compound_label), label_records in sorted(grouped.items()):
            names = sorted({record.molecule_name for record in label_records if record.molecule_name})
            pages = sorted({record.source.page for record in label_records if record.source.page is not None})
            property_names = sorted({record.property_name for record in label_records if record.property_name})
            resolved = any(_has_structure_identifier(record) for record in label_records)
            writer.writerow(
                {
                    "source_file": source_file,
                    "compound_label": compound_label,
                    "molecule_name": "; ".join(names),
                    "record_count": len(label_records),
                    "pages": "; ".join(str(page) for page in pages),
                    "property_names": "; ".join(property_names),
                    "structure_resolution_status": "resolved" if resolved else "unresolved_label",
                    "needs_structure_image_mapping": not resolved,
                }
            )


def _record_row(record: RawChemicalRecord) -> dict[str, object]:
    return {
        "record_id": record.record_id,
        "record_type": record.record_type,
        "source_file": record.source.source_file,
        "page": record.source.page,
        "section": record.source.section,
        "table_id": record.source.table_id,
        "figure_id": record.source.figure_id,
        "row_index": record.source.row_index,
        "extraction_method": record.source.extraction_method,
        "confidence": record.confidence,
        "compound_label": record.compound_label,
        "structure_id": record.structure_id,
        "image_id": record.image_id,
        "caption": record.caption,
        "crop_image_path": record.crop_image_path,
        "bbox_points": _bbox_value(record.bbox_points),
        "bbox_pixels": _bbox_value(record.bbox_pixels),
        "is_generic_structure": record.is_generic_structure,
        "generic_structure_reason": record.generic_structure_reason,
        "structure_resolution_status": "resolved" if _has_structure_identifier(record) else "unresolved_label",
        "needs_structure_image_mapping": bool(record.compound_label and not _has_structure_identifier(record)),
        "molecule_name": record.molecule_name,
        "formula": record.formula,
        "molecular_weight": record.molecular_weight,
        "SMILES": record.SMILES,
        "canonical_SMILES": record.canonical_SMILES,
        "isomeric_SMILES": record.isomeric_SMILES,
        "InChI": record.InChI,
        "InChIKey": record.InChIKey,
        "CAS": record.CAS,
        "property_name": record.property_name,
        "property_value": record.property_value,
        "unit": record.unit,
        "raw_value": record.raw_value,
        "validation_status": record.validation_status,
    }


def _has_structure_identifier(record: RawChemicalRecord) -> bool:
    if record.is_generic_structure or is_generic_structure(record.SMILES or record.canonical_SMILES, None):
        return False
    return any(
        [
            record.formula,
            record.SMILES,
            record.canonical_SMILES,
            record.isomeric_SMILES,
            record.InChI,
            record.InChIKey,
            record.CAS,
        ]
    )


def _bbox_value(bbox: object) -> str:
    if bbox is None:
        return ""
    if hasattr(bbox, "model_dump_json"):
        return bbox.model_dump_json()
    return str(bbox)
