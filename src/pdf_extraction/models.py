from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class SourceProvenance(BaseModel):
    source_file: str
    page: int | None = None
    section: str | None = None
    table_id: str | None = None
    figure_id: str | None = None
    row_index: int | None = None
    extraction_method: str
    confidence: float = Field(ge=0.0, le=1.0)


class ExtractedTextBlock(BaseModel):
    text: str
    source: SourceProvenance


class ExtractedTable(BaseModel):
    table_id: str
    rows: list[list[str]]
    source: SourceProvenance


class BoundingBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class ExtractedImageAsset(BaseModel):
    image_id: str
    path: str
    compound_label: str | None = None
    width: int | None = None
    height: int | None = None
    bbox: BoundingBox | None = None
    caption: str | None = None
    source: SourceProvenance


class RecognizedStructure(BaseModel):
    structure_id: str
    image_id: str | None = None
    compound_label: str | None = None
    bbox: BoundingBox | None = None
    smiles_raw: str | None = None
    canonical_SMILES: str | None = None
    isomeric_SMILES: str | None = None
    molfile: str | None = None
    reaction_smiles: str | None = None
    raw_output: str | None = None
    recognizer: str
    source: SourceProvenance
    confidence: float = Field(ge=0.0, le=1.0)


class IdentifierEnrichment(BaseModel):
    enrichment_id: str
    input_type: Literal["name", "smiles", "inchi", "inchikey", "cas", "pdb_id", "unknown"]
    input_value: str
    molecule_name: str | None = None
    CID: str | None = None
    canonical_SMILES: str | None = None
    isomeric_SMILES: str | None = None
    InChI: str | None = None
    InChIKey: str | None = None
    CAS: str | None = None
    PDB_ID: str | None = None
    source_database: str | None = None
    source_url: str | None = None
    source: SourceProvenance
    confidence: float = Field(ge=0.0, le=1.0)


class ValidationIssue(BaseModel):
    code: str
    message: str
    severity: Literal["info", "warning", "error"] = "warning"


class ValidationResult(BaseModel):
    target_id: str
    target_type: Literal["raw_record", "structure", "identifier_enrichment", "document"]
    status: Literal["not_checked", "valid", "warning", "invalid"]
    validator: str
    issues: list[ValidationIssue] = Field(default_factory=list)
    source: SourceProvenance | None = None


class RawChemicalRecord(BaseModel):
    record_id: str
    record_type: Literal["table_property", "text_property", "raw_table_row", "image_structure", "identifier_enrichment"]
    molecule_name: str | None = None
    formula: str | None = None
    molecular_weight: str | None = None
    SMILES: str | None = None
    canonical_SMILES: str | None = None
    isomeric_SMILES: str | None = None
    InChI: str | None = None
    InChIKey: str | None = None
    CAS: str | None = None
    compound_label: str | None = None
    structure_id: str | None = None
    image_id: str | None = None
    caption: str | None = None
    crop_image_path: str | None = None
    bbox_points: BoundingBox | None = None
    bbox_pixels: BoundingBox | None = None
    property_name: str | None = None
    property_value: str | None = None
    unit: str | None = None
    raw_value: str
    raw_row: list[str] | None = None
    source: SourceProvenance
    confidence: float = Field(ge=0.0, le=1.0)
    validation_status: str = "raw_unvalidated"


class ParsedPdfDocument(BaseModel):
    source_file: str
    page_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    text_blocks: list[ExtractedTextBlock] = Field(default_factory=list)
    tables: list[ExtractedTable] = Field(default_factory=list)
    images: list[ExtractedImageAsset] = Field(default_factory=list)
    recognized_structures: list[RecognizedStructure] = Field(default_factory=list)
    identifier_enrichments: list[IdentifierEnrichment] = Field(default_factory=list)
    validation_results: list[ValidationResult] = Field(default_factory=list)
    chemical_records: list[RawChemicalRecord] = Field(default_factory=list)


def stable_pdf_stem(pdf_path: Path) -> str:
    return pdf_path.stem.replace(" ", "_")
