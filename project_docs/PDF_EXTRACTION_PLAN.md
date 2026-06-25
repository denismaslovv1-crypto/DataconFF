# PDF Extraction Plan

## Goal

Build a reusable PDF parser for scientific chemical data extraction. The parser must not hardcode page numbers, molecule names, table layouts, or one specific article.

## Target Package

```text
src/pdf_extraction/
  pipeline.py
  models.py
  text_extractor.py
  table_extractor.py
  image_extractor.py
  ocr_extractor.py
  chemistry_extractor.py
  normalizer.py
  validator.py
  exporters.py
```

## Pipeline

```text
PDF input
  -> document inspection
  -> page-level text extraction
  -> table extraction
  -> image/figure extraction
  -> structure depiction segmentation
  -> structure recognition
  -> figure text/OCR property extraction
  -> OCR fallback when needed
  -> raw chemical record extraction
  -> normalization
  -> validation
  -> JSON/CSV export
```

## MVP Scope

The first useful workflow is:

```text
Given a scientific PDF, extract page-level text and table-like raw records into structured JSON with provenance.
```

MVP deliverables:

- CLI command for parsing a PDF.
- Page-level text extraction.
- Table extraction interface or implementation.
- Pydantic models for raw extracted items and source provenance.
- Structured JSON output.
- Basic fixtures/tests.
- Documentation explaining how to run the parser.

## Provenance Model

Each raw item should preserve:

```text
source file -> page -> section/table/figure -> extraction method -> confidence
```

Raw extracted values must not be overwritten by normalization. Normalized records should point back to raw records.

## Suggested Tool Choices

Start local and modular:

- Text extraction: PyMuPDF or pdfplumber.
- Table extraction: pdfplumber first; Camelot later when lattice/stream modes are needed.
- Image extraction: PyMuPDF.
- Chemical structure segmentation: DECIMER Segmentation as an optional external environment.
- Structure recognition: MolScribe as an optional external environment.
- OCR fallback: Tesseract/PaddleOCR as optional module.
- Article structure: Docling/GROBID as optional advanced module.
- Chemistry validation: RDKit later, behind a validator interface.

## Generic Structure Rule

Structure depictions containing `R`, `R1`, `R2`, `Ar`, or similar variable substituent labels are scaffolds, not complete molecules. If recognition produces wildcard SMILES with `*`, keep the record but mark it as generic:

```text
is_generic_structure=True
validation_status=generic_structure_unresolved
```

Generic structures must not resolve compound labels. They become candidates for later scaffold/substituent reconstruction only after substituent definitions are extracted from source tables, captions, or surrounding text.

Text printed inside or near figures, such as IC50 values or binding assay results, must be extracted as figure-property records with provenance. It should not be merged into the structure-recognition result.

## Non-goals For MVP

- No audio transcription.
- No complex multi-agent orchestration.
- No one-off parser hardcoded for a single PDF.
- No silent dropping of source references.
