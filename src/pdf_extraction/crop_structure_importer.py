from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pdf_extraction.exporters import write_compound_labels_csv, write_document_json, write_records_csv
from pdf_extraction.models import (
    BoundingBox,
    ExtractedImageAsset,
    ParsedPdfDocument,
    RawChemicalRecord,
    RecognizedStructure,
    SourceProvenance,
    stable_pdf_stem,
)
from pdf_extraction.structure_quality import generic_structure_reason
from pdf_extraction.structure_mapper import apply_structure_mappings, structures_to_records


def import_molscribe_crop(
    output_dir: Path,
    sidecar_path: Path,
    molscribe_json_path: Path,
    figure_id: str | None = None,
    caption: str | None = None,
    compound_label: str | None = None,
    min_confidence: float = 0.0,
) -> ParsedPdfDocument:
    sidecar = _read_json(sidecar_path)
    molscribe = _read_json(molscribe_json_path)
    confidence = float(molscribe.get("confidence", 0.5))
    if confidence < min_confidence:
        raise ValueError(f"MolScribe confidence {confidence:.4f} is below threshold {min_confidence:.4f}")

    source_file = str(sidecar["source_file"])
    document_path = output_dir / f"{stable_pdf_stem(Path(source_file))}.raw.json"
    if not document_path.exists():
        raise FileNotFoundError(
            f"Parsed document JSON not found: {document_path}. Run the PDF pipeline before importing crop structures."
        )

    document = ParsedPdfDocument.model_validate(_read_json(document_path))
    crop_id = str(sidecar.get("crop_id") or Path(str(sidecar["image_path"])).stem)
    resolved_figure_id = figure_id or _infer_figure_id(crop_id)
    bbox_points = _bbox_from_mapping(sidecar.get("bbox_points"))
    bbox_pixels = _bbox_from_mapping(sidecar.get("bbox_pixels"))
    smiles = molscribe.get("smiles")
    canonical_smiles = molscribe.get("canonical_SMILES") or molscribe.get("canonical_smiles")
    molfile = molscribe.get("molfile")
    generic_reason = generic_structure_reason(smiles or canonical_smiles, molfile)

    image = ExtractedImageAsset(
        image_id=crop_id,
        path=str(sidecar["image_path"]),
        compound_label=compound_label,
        width=sidecar.get("image_width"),
        height=sidecar.get("image_height"),
        bbox=bbox_points,
        caption=caption,
        source=SourceProvenance(
            source_file=source_file,
            page=sidecar.get("page"),
            figure_id=resolved_figure_id,
            extraction_method=str(sidecar.get("extraction_method", "pymupdf.page_clip_render")),
            confidence=float(sidecar.get("confidence", 1.0)),
        ),
    )
    structure = RecognizedStructure(
        structure_id=f"{crop_id}_molscribe",
        image_id=crop_id,
        compound_label=compound_label,
        bbox=bbox_points,
        smiles_raw=smiles,
        canonical_SMILES=canonical_smiles,
        isomeric_SMILES=molscribe.get("isomeric_SMILES") or molscribe.get("isomeric_smiles"),
        molfile=molfile,
        raw_output=json.dumps(molscribe, ensure_ascii=False),
        recognizer="molscribe",
        is_generic_structure=generic_reason is not None,
        generic_structure_reason=generic_reason,
        source=SourceProvenance(
            source_file=source_file,
            page=sidecar.get("page"),
            figure_id=resolved_figure_id,
            extraction_method="external_molscribe",
            confidence=confidence,
        ),
        confidence=confidence,
    )

    document.images = _replace_by_id(document.images, image, "image_id")
    document.recognized_structures = _replace_by_id(document.recognized_structures, structure, "structure_id")
    document.chemical_records = _without_record(document.chemical_records, f"{structure.structure_id}_image_structure")
    document.chemical_records = apply_structure_mappings(document.chemical_records, [structure])
    structure_records = structures_to_records(source_file, [structure])
    for record in structure_records:
        record.caption = caption
        record.crop_image_path = image.path
        record.bbox_points = bbox_points
        record.bbox_pixels = bbox_pixels
    document.chemical_records.extend(structure_records)

    write_document_json(document, document_path)
    rebuild_output_csv(output_dir)
    return document


def rebuild_output_csv(output_dir: Path) -> list[RawChemicalRecord]:
    records: list[RawChemicalRecord] = []
    for path in sorted(output_dir.glob("*.raw.json")):
        document = ParsedPdfDocument.model_validate(_read_json(path))
        records.extend(document.chemical_records)
    write_records_csv(records, output_dir / "chemical_records.csv")
    write_compound_labels_csv(records, output_dir / "compound_labels.csv")
    return records


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _bbox_from_mapping(value: Any) -> BoundingBox | None:
    if not isinstance(value, dict):
        return None
    return BoundingBox(x0=value["x0"], y0=value["y0"], x1=value["x1"], y1=value["y1"])


def _replace_by_id(items: list[Any], replacement: Any, id_field: str) -> list[Any]:
    replacement_id = getattr(replacement, id_field)
    replaced = False
    result: list[Any] = []
    for item in items:
        if getattr(item, id_field) == replacement_id:
            result.append(replacement)
            replaced = True
        else:
            result.append(item)
    if not replaced:
        result.append(replacement)
    return result


def _without_record(records: list[RawChemicalRecord], record_id: str) -> list[RawChemicalRecord]:
    return [record for record in records if record.record_id != record_id]


def _infer_figure_id(crop_id: str) -> str | None:
    lowered = crop_id.lower()
    marker = "fig"
    index = lowered.find(marker)
    if index < 0:
        return None
    start = index + len(marker)
    digits = []
    for character in lowered[start:]:
        if character.isdigit():
            digits.append(character)
            continue
        break
    if not digits:
        return None
    return f"Figure {''.join(digits)}"
