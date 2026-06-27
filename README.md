# DataCon ChemX Benzimidazoles Extraction

This repository contains a reproducible ChemX information extraction workflow
for the DataCon final task. It focuses on the `Benzimidazoles` domain and turns
scientific PDFs into ChemX-compatible prediction CSV files, then evaluates them
with the repository's local evaluator.

The final submitted path is deterministic and rules-only:

```text
PDF -> parser -> evidence -> rule extraction -> normalization -> validation -> ChemX CSV -> evaluation -> Streamlit UI
```

RAG, LLM fallback, multi-agent workflows, MolScribe, DECIMER, YOLO, OCR stacks,
and full image-based structure recognition are not required for the final
rules-only result.

## Final Result

The final saved full Benzimidazoles rules-only run is:

```text
outputs/benzimidazoles_full/
```

It completed 31/31 locally available PDFs and produced:

| Metric | Value |
|---|---:|
| Predictions | 2247 |
| Ground-truth rows | 1721 |
| Local evaluator Macro-F1 | 0.4622 |
| Published single-agent baseline | 0.217 |

This exceeds the published single-agent baseline under the repository's local
evaluator. The evaluator is an approximation of benchmark behavior, not a claim
of official scorer parity.

Key extraction improvements in the final path:

- source-backed `target_units` extraction from table titles, headers, and
  compact OCR forms such as `µmolmL−1`, `µg mL−1`, and `mg L−1`;
- table-like antibacterial MIC extraction for compound IDs such as `BK-1` to
  `BK-11`, keeping only supported `S. aureus` and `E. coli` columns;
- compact antimicrobial MIC table extraction for headers such as
  `Bc Sa Pa Ec Ab Ca`, keeping the supported `Sa` and `Ec` columns;
- evidence-aware export deduplication: records with the same ChemX values are
  merged only when they come from the same `evidence_id`, while repeated
  mentions from distinct evidence contexts are preserved;
- metric/reporting safeguards for PDF-stem ground-truth matching and
  metric-only canonicalization of numeric values and bacteria aliases.

See [RESULTS.md](RESULTS.md) for field metrics and caveats.

## Installation

Create the repository-local environment:

```powershell
.\setup_project_env.cmd
```

Install the final public requirements in the repository environment if needed:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Use only the repository-local interpreter for project commands:

```powershell
.\.venv\Scripts\python.exe
```

## Full Rules-Only Run

Run the reproducible full Benzimidazoles rules-only workflow:

```powershell
.\.venv\Scripts\python.exe scripts\run_benzimidazoles_full.py `
  --pdf-dir data\chemx\benzimidazoles\pdfs `
  --ground-truth data\chemx\benzimidazoles\ground_truth.csv `
  --output-dir outputs\benzimidazoles_full
```

The command writes per-article artifacts and merged outputs under the selected
output directory. The default mode is rules-only; internal LLM fallback hooks
remain available for experiments but are not used by this public command or by
the reported metrics.

Important output files:

```text
predictions.csv              ChemX-compatible merged prediction rows
review_records.csv/.json     review-only source/evidence context sidecars
metrics.json                 aggregate local evaluation metrics
field_metrics.csv            field-level precision, recall, and F1
article_summary.csv          per-PDF status, prediction counts, and metrics
run_manifest.json            reproducibility metadata
```

## Streamlit Review UI

Run the local review UI:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The final UI has three review modes:

- `Saved Full-Run Results`: load an existing output directory and inspect
  aggregate metrics, article summaries, field metrics, zero-row/low-row PDFs,
  predictions, evidence/review context, duplicate diagnostics, and downloads.
- `Run Single Article`: select or upload one PDF, run the rules-only
  Benzimidazoles workflow with corrected PDF-stem evaluation, and inspect
  predictions, validation errors, field metrics, evidence, and review
  provenance.
- `Run Full Dataset`: run the documented full rules-only command after explicit
  confirmation, then load the resulting output directory in the saved-results
  view.

## Limitations

- Scope is one ChemX domain: `Benzimidazoles`.
- The final public run is rules-only; no LLM calls are used.
- SMILES remain unresolved and are exported as `NOT_DETECTED`.
- Full image/structure recognition is not used.
- LLM-based SMILES or structure extraction may be future work, but it was not
  included in the final evaluated run.
- The local evaluator is approximate and should be interpreted as a local
  reproducibility metric.
- Recall remains limited, and performance is uneven across PDFs.

## Public Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [RESULTS.md](RESULTS.md)
