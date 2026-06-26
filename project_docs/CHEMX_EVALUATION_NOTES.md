# ChemX Evaluation Notes

## Purpose

This file captures how to evaluate the project against ChemX and how to avoid optimizing the wrong target.

## Main evaluation target

ChemX evaluates extracted records by field-level:

- Precision;
- Recall;
- F1;
- Macro-F1 across target fields.

The hackathon objective is to beat the published single-agent baseline on at least one domain.

## Primary domain: Benzimidazoles

Target CSV columns:

```text
compound_id, smiles, target_type, target_relation, target_value, target_units, bacteria
```

Published single-agent baseline target:

```text
Macro-F1 = 0.217
```

The exact evaluator may compare strings, numbers, and missing values differently by field, so the predictions file must keep the benchmark column names exactly.

## Field priority

Optimize fields in this order:

1. `compound_id`
2. `target_type`
3. `target_relation`
4. `target_value`
5. `target_units`
6. `bacteria`
7. `smiles`

`smiles` is low priority for the first positive result because automated SMILES extraction is often weak in the baseline and can consume too much time. Use `NOT_DETECTED` instead of hallucinating.

## Prediction output requirements

Every run should save:

```text
outputs/benzimidazoles/predictions.csv
outputs/benzimidazoles/predictions.json
outputs/benzimidazoles/metrics.json
outputs/benzimidazoles/field_metrics.csv
```

`predictions.csv` must contain only benchmark-compatible target columns unless the evaluator explicitly supports additional ignored columns.

`predictions.json` may contain extra provenance fields:

```text
source_file
page
section
table_id
row_id
evidence_text
extraction_method
confidence
validation_status
```

## Missing values

Use:

```text
NOT_DETECTED
```

Do not use arbitrary alternatives such as `NaN`, empty string, `None`, or `unknown` unless the official evaluator requires them.

## Matching and normalization risks

Common issues that reduce F1:

- wrong column names;
- extra columns passed to strict evaluator;
- `ug/mL`, `µg/mL`, and `μg/mL` mismatches;
- missing relation signs, especially default `=`;
- bacteria aliases not normalized;
- ranges treated inconsistently;
- false positive rows from broad LLM extraction;
- LLM-invented SMILES or values;
- table row split/merge errors.

## Evaluation loop

Use this order:

1. Produce a small predictions file for a few PDFs.
2. Run evaluator.
3. Inspect field-level F1.
4. Fix the worst high-priority field.
5. Re-run.
6. Only after beating the baseline, add UI and README polish.

## Suggested local commands

Use the repository-local interpreter:

```powershell
.\.venv\Scripts\python.exe scripts\run_domain.py --domain benzimidazoles
.\.venv\Scripts\python.exe scripts\evaluate_domain.py --domain benzimidazoles
```

Do not use plain `python`, `python3`, `py`, or a system interpreter.

## Positive result update rule

After the system reliably beats the single-agent baseline on a stable validation/test subset:

1. Update `DATACON_EXECUTION_CHECKLIST.md`.
2. Move from `Benzimidazoles-only MVP` to `stabilization / fallback domain`.
3. Save final metrics under `outputs/benzimidazoles/`.
4. Add a short note to `project_docs/DECISIONS.md`.
5. Do not overwrite earlier metrics; keep run history.
