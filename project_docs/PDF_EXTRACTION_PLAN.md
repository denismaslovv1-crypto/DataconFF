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
- OCR fallback: Tesseract/PaddleOCR as optional module.
- Article structure: Docling/GROBID as optional advanced module.
- Chemistry validation: RDKit later, behind a validator interface.

## Non-goals For MVP

- No audio transcription.
- No complex multi-agent orchestration.
- No one-off parser hardcoded for a single PDF.
- No silent dropping of source references.

