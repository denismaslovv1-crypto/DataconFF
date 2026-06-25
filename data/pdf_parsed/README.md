# PDF Chemical Records Export

This folder contains generated outputs from the reusable PDF extraction MVP.

## Inputs

Raw PDFs are read from:

```text
data/pdf_raw/
```

## Outputs

```text
data/pdf_parsed/
  chemical_records.csv      # long-form raw chemical/property candidates
  compound_labels.csv       # unique source_file + compound_label values to resolve from structures
  *.raw.json                # per-PDF raw extraction with text, tables, records, provenance
```

## Processing

The parser follows the project RAG decision: first build one useful PDF-to-record workflow, then expand it into normalizer, validator, exporter, and agent stages.

Current stages:

1. Page-level text extraction with `pdfplumber`.
2. Table extraction with `pdfplumber`.
3. Heuristic chemical row detection from extracted tables and table-like text lines.
4. Optional no-op hooks for image extraction, structure recognition, identifier enrichment, and validation.
5. Raw JSON export preserving source provenance.
6. Long-form CSV export for database preparation.

Chemical identifiers such as `SMILES`, canonical `SMILES`, `InChI`, `InChIKey`, `CID`, and `PDB ID` are not inferred from PDF text in the current pipeline. They are expected to come from image/structure recognition outputs, then optional database enrichment and validation.

Rows with only `compound_label` are valid raw assay/property records, not fully resolved molecules. Use `compound_labels.csv` as the worklist for mapping article labels such as `4d` or `15a` to structures extracted from figures/schemes.

Every CSV row keeps provenance:

```text
source_file -> page -> section/table -> row_index -> extraction_method -> confidence
```

The CSV is raw and unvalidated. It is intended as the first database layer before normalization, chemistry validation, and manual/agent review.

## Run

From the project root:

```powershell
$env:PYTHONPATH = "src"
python -m pdf_extraction data/pdf_raw --output-dir data/pdf_parsed
```

Or after installing the package script:

```powershell
datacon-pdf data/pdf_raw --output-dir data/pdf_parsed
```

## Optional Stage Hooks

The pipeline is ready for future adapters without enabling heavy tools by default:

```text
image_extractor        # PyMuPDF/page renders/figure crops later
structure_recognizer   # YOLO + MolScribe/OSRA/RxnScribe later
identifier_enricher    # PubChem/OPSIN/RCSB PDB later
validator              # RDKit/range/unit validation later
```

The CLI flag exists for testing configured hooks:

```powershell
$env:PYTHONPATH = "src"
python -m pdf_extraction data/pdf_raw --output-dir data/pdf_parsed --run-optional-stages
```

With the current default adapters this is still no-op for heavy stages.

Use a tool config to connect local image and structure tools:

```powershell
$env:PYTHONPATH = "src"
python -m pdf_extraction --tool-config config/pdf_tools.example.json
```

In `config/pdf_tools.example.json`, enable only tools installed locally:

```text
PyMuPDF image extraction -> embedded images/page renders
YOLO command             -> molecule/reaction crop manifest
MolScribe command        -> JSON with smiles/molfile/confidence
OSRA command             -> SMILES lines
RxnScribe command        -> JSON reaction predictions
```

The expected YOLO manifest format is:

```json
{
  "detections": [
    {
      "image_id": "crop_id",
      "image_path": "path/to/crop.png",
      "bbox": {"x0": 1, "y0": 2, "x1": 100, "y1": 120},
      "confidence": 0.91
    }
  ]
}
```

MolScribe JSON stdout should contain:

```json
{"smiles": "CCO", "molfile": "...", "confidence": 0.9}
```

RxnScribe JSON stdout should contain:

```json
{"reactions": [{"reactants": [], "conditions": [], "products": []}]}
```
