from __future__ import annotations

from dataclasses import replace

from pdf_extraction.models import RawChemicalRecord, RecognizedStructure, SourceProvenance


def structures_to_records(source_file: str, structures: list[RecognizedStructure]) -> list[RawChemicalRecord]:
    records: list[RawChemicalRecord] = []
    for structure in structures:
        value = structure.smiles_raw or structure.molfile or structure.reaction_smiles or structure.raw_output or ""
        records.append(
            RawChemicalRecord(
                record_id=f"{structure.structure_id}_image_structure",
                record_type="image_structure",
                compound_label=structure.compound_label,
                structure_id=structure.structure_id,
                image_id=structure.image_id,
                SMILES=structure.smiles_raw,
                canonical_SMILES=structure.canonical_SMILES,
                isomeric_SMILES=structure.isomeric_SMILES,
                raw_value=value,
                source=SourceProvenance(
                    source_file=source_file,
                    page=structure.source.page,
                    figure_id=structure.source.figure_id,
                    extraction_method=structure.source.extraction_method,
                    confidence=structure.confidence,
                ),
                confidence=structure.confidence,
                validation_status="raw_unvalidated",
            )
        )
    return records


def apply_structure_mappings(
    records: list[RawChemicalRecord],
    structures: list[RecognizedStructure],
) -> list[RawChemicalRecord]:
    """Fill structure identifiers on table/text records when labels match.

    This is intentionally conservative: only structures that already carry a
    compound_label are mapped. Label detection/OCR/crop naming should happen in
    the image or YOLO/RxnScribe stage.
    """

    by_label: dict[str, RecognizedStructure] = {}
    for structure in structures:
        if structure.compound_label and structure.compound_label not in by_label:
            by_label[structure.compound_label] = structure

    mapped: list[RawChemicalRecord] = []
    for record in records:
        structure = by_label.get(record.compound_label or "")
        if not structure:
            mapped.append(record)
            continue
        data = record.model_copy(
            update={
                "structure_id": structure.structure_id,
                "image_id": structure.image_id,
                "SMILES": record.SMILES or structure.smiles_raw,
                "canonical_SMILES": record.canonical_SMILES or structure.canonical_SMILES,
                "isomeric_SMILES": record.isomeric_SMILES or structure.isomeric_SMILES,
                "validation_status": "structure_mapped_unvalidated",
            }
        )
        mapped.append(data)
    return mapped
