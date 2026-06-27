# Architecture

The public submission uses a deterministic, rules-only ChemX extraction
pipeline for the `Benzimidazoles` domain.

```text
scientific PDF
  -> local PDF parser
  -> text/table evidence chunks
  -> Benzimidazoles rule extraction
  -> normalization
  -> strict validation
  -> ChemX-compatible CSV/JSON export
  -> local evaluation
  -> Streamlit review UI
```

## Runtime Components

`pdf_extraction` parses each PDF into text blocks, tables, and provenance. The
final run uses text/table evidence only; image-based structure recognition is
not part of the public result.

`datacon_workflow.extraction` builds evidence chunks and applies
Benzimidazoles-specific rule extractors. The final extractor covers:

- MIC/pMIC prose snippets;
- table-like MIC evidence where units are carried by the table title/header;
- compact/OCR unit forms such as `µmolmL−1`, `µg mL−1`, and `mg L−1`;
- antibacterial tables with compound IDs such as `BK-1` to `BK-11`, extracting
  supported `S. aureus` and `E. coli` columns only.
- compact antimicrobial tables with abbreviation headers such as
  `Bc Sa Pa Ec Ab Ca`, extracting supported `Sa` and `Ec` columns only.

`datacon_workflow.normalization` normalizes values for export while preserving
raw evidence separately. It does not invent missing values.

`datacon_workflow.validation` keeps validation strict. Required evidence-backed
values must be present before records are exported. Missing values remain
`NOT_DETECTED` and unsupported records are rejected instead of patched.

`datacon_workflow.export` writes ChemX-compatible outputs with the exact column
order:

```text
compound_id,smiles,target_type,target_relation,target_value,target_units,bacteria
```

Final export deduplication is evidence-aware: records with the same ChemX
values are merged only when they come from the same `evidence_id`. Repeated
mentions from distinct evidence contexts are preserved.

`datacon_workflow.review_records` writes review-only sidecars
(`review_records.csv` and `review_records.json`) that link ChemX rows to
article/source context, page, evidence text, extractor, confidence, detected
compound mentions, and duplicate status. These fields are not added to the
benchmark-compatible `predictions.csv`.

`datacon_workflow.evaluation` computes local field-level precision, recall, F1,
and Macro-F1. Per-article reporting should scope ground truth by PDF stem and
uses metric-only canonicalization for harmless serialization differences such
as `5` versus `5.0` and common bacteria aliases.

`app.py` provides the final Streamlit review UI. It is organized around:

- saved full-run results, including aggregate metrics, article summary,
  field metrics, zero-row/low-row highlights, predictions, evidence/review
  context, duplicate diagnostics, and downloads;
- rules-only single-article runs with corrected PDF-stem evaluation and
  evidence/provenance review;
- explicit-confirmation full-dataset runs of the documented rules-only command.

## Final Submission Path

The full public result is produced by:

```powershell
.\.venv\Scripts\python.exe scripts\run_benzimidazoles_full.py `
  --pdf-dir data\chemx\benzimidazoles\pdfs `
  --ground-truth data\chemx\benzimidazoles\ground_truth.csv `
  --output-dir outputs\benzimidazoles_full
```

Final saved aggregate result:

```text
outputs/benzimidazoles_full/
Macro-F1: 0.4622
Predictions: 2247
Ground-truth rows: 1721
PDFs completed: 31/31 locally available
```

## Invariants

- Keep stages separate: extraction, normalization, validation, export, and
  evaluation.
- Preserve source provenance: file, page, table/text context, method, and
  confidence where available.
- Do not use ground truth, previous predictions, metrics, or benchmark-derived
  fixes as extraction input.
- Do not relax validation to improve score.
- Do not make LLM calls in the final rules-only run.

## Non-Required Experimental Features

The repository contains internal development code and notes for RAG support,
LLM fallback, optional agentic sidecars, MolScribe, DECIMER, YOLO, and related
structure-recognition experiments. These are not required for the final
rules-only Benzimidazoles result and are not part of the public claim.
LLM-based SMILES or structure extraction remains possible future work, but it
was not included in the final evaluated run.
