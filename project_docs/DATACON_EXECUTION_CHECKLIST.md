# DataCon ChemX execution checklist

This checklist is a living project artifact. Update it whenever the extraction workflow shows a stable positive result, a new bottleneck is discovered, or the selected domain strategy changes.

## Status legend

```text
[ ] not started
[~] in progress
[x] done
[!] blocked or needs decision
[-] postponed intentionally
```

## Stable positive result rule

A result is considered stable and positive only when all of the following are true:

```text
- the workflow runs end-to-end from input PDF/data to ChemX-compatible CSV
- the run is reproducible from committed code/config
- the output is evaluated with Macro-F1 and field-level F1
- the selected domain Macro-F1 exceeds the published single-agent baseline, or a documented field-level improvement is achieved without lowering current Macro-F1
- tests pass, or known failures are documented with a reason
```

When this happens:

```text
1. Mark the relevant checklist items as [x].
2. Record metrics in outputs/<domain>/metrics.json and reports/final_metrics.md.
3. Add the next improvement or next-domain checklist section.
4. Update README commands if the workflow changed.
```

## Scope lock

- [ ] Confirm primary domain: `Benzimidazoles`.
- [ ] Confirm fallback domains: `Complexes`, `Co-crystals`.
- [ ] Confirm that the first target is one positive domain, not all ChemX domains.
- [ ] Confirm selected UI stack: Streamlit or Gradio.
- [ ] Confirm evaluation command and expected ground-truth location.
- [ ] Confirm local interpreter path: `.\.venv\Scripts\python.exe`.

## Project documentation

- [ ] Replace/update `AGENTS.md` with ChemX-specific rules.
- [ ] Add `project_docs/DATACON_FINAL_TASK_BRIEF.md`.
- [ ] Add `project_docs/DATACON_EXECUTION_CHECKLIST.md`.
- [ ] Update README with exact run commands using `.\.venv\Scripts\python.exe`.
- [ ] Document current target domain and baseline Macro-F1.
- [ ] Document known limitations and postponed work.

## Existing project audit

- [ ] Identify reusable components from `src/pdf_extraction`.
- [ ] Identify reusable components from `src/rag_core`.
- [ ] Identify reusable parser/enrichment examples from `code_examples`.
- [ ] Check current tests and record baseline test result.
- [ ] Check existing `data/pdf_raw` and `data/pdf_parsed` artifacts.
- [ ] Identify gaps between current raw records and ChemX prediction schema.

## ChemX data and evaluation

- [ ] Download or connect the Benzimidazoles dataset.
- [ ] Locate ground-truth CSV/table for Benzimidazoles.
- [ ] Locate source PDFs or article references for evaluation.
- [ ] Inspect column names, types, missing-value format, and examples.
- [ ] Implement or wrap ChemX-compatible evaluation.
- [ ] Save baseline evaluation output for an empty/minimal prediction.
- [ ] Save evaluation reports under `outputs/benzimidazoles/`.

## Domain schema

- [ ] Add Benzimidazoles domain config.
- [ ] Add Pydantic schema for Benzimidazoles records.
- [ ] Enforce exact CSV columns:
  - [ ] `compound_id`
  - [ ] `smiles`
  - [ ] `target_type`
  - [ ] `target_relation`
  - [ ] `target_value`
  - [ ] `target_units`
  - [ ] `bacteria`
- [ ] Add `NOT_DETECTED` handling.
- [ ] Add tests for column order and missing values.

## Evidence extraction

- [ ] Reuse existing PDF parser for text and tables.
- [ ] Build evidence chunks from tables.
- [ ] Build evidence chunks from table-like text.
- [ ] Build text snippets around MIC/pMIC mentions.
- [ ] Build text snippets around bacteria aliases.
- [ ] Preserve page, table/row, source file, method, and confidence where possible.
- [ ] Save evidence artifacts for debugging.

## Rule-based Benzimidazoles extraction

- [ ] Extract `compound_id` from article-local identifiers.
- [ ] Extract `target_type`: MIC / pMIC.
- [ ] Extract `target_relation`: `=`, `<`, `>`.
- [ ] Extract `target_value`.
- [ ] Extract `target_units`.
- [ ] Extract `bacteria`.
- [ ] Set `smiles` to `NOT_DETECTED` unless source-backed.
- [ ] Add tests for relation parsing.
- [ ] Add tests for MIC/pMIC value parsing.
- [ ] Add tests for bacteria alias handling.

## Optional LLM extraction

- [ ] Add LLM extractor over evidence chunks only.
- [ ] Require JSON array output only.
- [ ] Validate every LLM record with Pydantic.
- [ ] Reject unsupported records without evidence.
- [ ] Add retry/repair only for JSON syntax errors, not for missing evidence.
- [ ] Compare rules-only vs rules-plus-LLM metrics.

## Normalization

- [ ] Normalize relation symbols.
- [ ] Normalize obvious unit variants, for example `ug/mL`, `µg/mL`, `μg/mL`.
- [ ] Normalize bacteria aliases only when it improves benchmark compatibility.
- [ ] Preserve raw value and raw unit in JSON/debug artifacts when possible.
- [ ] Do not normalize away evidence.

## Validation

- [ ] Validate required columns.
- [ ] Validate field types.
- [ ] Validate allowed target types.
- [ ] Validate allowed relation symbols.
- [ ] Validate numeric values and supported ranges.
- [ ] Mark low-confidence or unsupported records.
- [ ] Save rejected records for analysis.

## Export

- [ ] Export `outputs/benzimidazoles/predictions.csv`.
- [ ] Export `outputs/benzimidazoles/predictions.json` with evidence/debug metadata.
- [ ] Export `outputs/benzimidazoles/field_metrics.csv`.
- [ ] Export `outputs/benzimidazoles/metrics.json`.
- [ ] Ensure prediction CSV has no unexpected columns.

## Evaluation loop

- [ ] Run first full evaluation.
- [ ] Record Macro-F1.
- [ ] Record field-level F1.
- [ ] Identify top false-positive causes.
- [ ] Identify top false-negative causes.
- [ ] Improve only the highest-impact bottleneck.
- [ ] Re-run evaluation after every meaningful change.
- [ ] Save comparison notes for each major run.

## Web UI

- [ ] Add minimal Streamlit/Gradio app.
- [ ] Add PDF upload or PDF selection.
- [ ] Add domain selector.
- [ ] Add extraction run button.
- [ ] Display extracted records as a table.
- [ ] Display validation status.
- [ ] Display evidence/provenance for selected record when available.
- [ ] Add CSV/JSON download.
- [ ] Add a demo PDF or documented demo path.

## Tests and reproducibility

- [ ] Run existing test suite.
- [ ] Add tests for new domain schema.
- [ ] Add tests for exporter.
- [ ] Add tests for parser helpers.
- [ ] Add tests for normalizers.
- [ ] Add tests for validators.
- [ ] Ensure README commands work from a fresh checkout.
- [ ] Avoid system Python in docs and scripts.

## Positive result gate: Benzimidazoles

- [ ] End-to-end Benzimidazoles run completed.
- [ ] Prediction CSV is benchmark-compatible.
- [ ] Macro-F1 is computed.
- [ ] Macro-F1 exceeds Benzimidazoles single-agent baseline `0.217`.
- [ ] Positive result reproduced after a clean rerun.
- [ ] Metrics report saved.
- [ ] README updated.
- [ ] Demo UI confirmed working.

## 2026-06-26 checked per-article baseline

- [x] End-to-end deterministic run completed for
  `data/chemx/benzimidazoles/pdfs/janupally2014.pdf`.
- [x] `outputs/benzimidazoles/janupally/predictions.csv` uses the exact seven
  ChemX columns and contains 82 validated MIC records.
- [x] Scoped evaluation found DOI `10.1016/j.bmc.2014.09.008` in the parsed
  PDF and compared against its 82 matching benchmark rows.
- [x] This per-article run produced Macro-F1 `0.8554`; field-level metrics are
  saved beside the output.
- [x] The project test suite passed: `28 passed`.
- [ ] Repeat over every locally available benchmark PDF before claiming a
  dataset-level positive result or marking the full gate complete.

## Expansion after stable positive result

Only start this section after the Benzimidazoles positive result gate is passed.

- [ ] Choose next domain based on lowest implementation risk.
- [ ] Add next domain config.
- [ ] Add next domain schema.
- [ ] Reuse evidence builder.
- [ ] Implement domain-specific extractor.
- [ ] Run domain evaluation.
- [ ] Update metrics report.
- [ ] Update presentation/demo story.

## Postponed unless everything above works

- [-] Full autonomous multi-agent swarm.
- [-] Universal extraction across all ChemX domains.
- [-] Heavy OCR stack integration.
- [-] DECIMER/MolScribe/YOLO integration unless already configured.
- [-] Full evidence graph database.
- [-] Human review UI beyond simple evidence display.
- [-] Complex chart digitization.
- [-] Production-grade deployment.
