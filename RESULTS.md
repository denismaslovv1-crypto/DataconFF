# Results

The final saved Benzimidazoles rules-only run is:

```text
outputs/benzimidazoles_full/
```

It completed the locally available Benzimidazoles PDF set and exceeds the
published single-agent baseline under the repository's local evaluator.

## Summary

| Metric | Value |
|---|---:|
| Domain | Benzimidazoles |
| Mode | rules-only |
| PDFs completed | 31/31 locally available |
| Predictions | 2247 |
| Ground-truth rows | 1721 |
| Local evaluator Macro-F1 | 0.4622 |
| Published single-agent baseline | 0.217 |

## Field Metrics

From `outputs/benzimidazoles_full/field_metrics.csv`:

| Field | Precision | Recall | F1 | True positive |
|---|---:|---:|---:|---:|
| compound_id | 0.1713 | 0.2237 | 0.1941 | 385 |
| smiles | 0.0000 | 0.0000 | 0.0000 | 0 |
| target_type | 0.7459 | 0.9739 | 0.8448 | 1676 |
| target_relation | 0.7183 | 0.9378 | 0.8135 | 1614 |
| target_value | 0.3427 | 0.4474 | 0.3881 | 770 |
| target_units | 0.5376 | 0.7019 | 0.6089 | 1208 |
| bacteria | 0.3409 | 0.4451 | 0.3861 | 766 |

## What Improved

The final rules-only path includes several source-backed extraction
improvements:

- `target_units` extraction now uses source-backed units from the same evidence
  chunk, including table titles/headers such as `(MIC, µM)`, `(MIC, mg/L)`,
  and compact/OCR forms such as `MIC=12.5µmolmL−1`.
- Table-like antibacterial MIC extraction supports compound IDs such as
  `BK-1` through `BK-11` and keeps only supported `S. aureus` and `E. coli`
  columns, ignoring fungal, antioxidant, DPPH, NO, and unsupported bacterial
  columns.
- Compact antimicrobial MIC tables with organism abbreviation headers such as
  `Bc Sa Pa Ec Ab Ca` are parsed by column position. The final extractor keeps
  the supported `Sa` and `Ec` columns and ignores unsupported organisms and
  standards.
- Final export deduplication is evidence-aware: records with the same ChemX
  values are merged only when they come from the same `evidence_id`. Repeated
  mentions from distinct evidence contexts are preserved.

These changes reduced zero-row failures, recovered `jhet.3467.pdf` to 22
source-backed prediction rows in final artifacts, and recovered
`s13065-018-0479-1.pdf` to 24 validated rows in single-article verification.
The complete local run also includes the newly available
`1570180811666140725185713.pdf`; for that article, one header-only MIC
candidate was correctly rejected because it lacked source-backed bacteria and a
decodable unit.

## Evaluation Consistency

Evaluation/reporting now treats ground-truth matching as a PDF identity problem:
GT scoping should use the PDF stem, with DOI matches as supporting metadata
rather than the only filter. This avoids malformed DOI extraction causing
incorrect per-article `gt_rows`.

Metric comparison also uses metric-only canonicalization for serialization
differences:

- numeric values such as `5`, `5.0`, and `5.00` compare equal;
- bacteria aliases such as `S. aureus` and `Staphylococcus aureus` compare
  equal, likewise `E. coli` and `Escherichia coli`.

These canonicalizations are for evaluation only; they do not relax validation
or rewrite raw extracted evidence.

## Caveats

- The local evaluator is an approximation and is not claimed to match the
  official scorer exactly.
- The final claim is scoped to the Benzimidazoles domain.
- The final public run is rules-only and uses no LLM calls.
- SMILES are unresolved, so the `smiles` field remains at F1 `0.0000`.
- Full image/structure recognition was not used.
- Recall remains limited and results are uneven across PDFs.

## Streamlit Review UI

The final Streamlit UI is a commission-facing review surface, not a chatbot.
It has three modes:

- saved full-run results: aggregate metrics, article summary, field metrics,
  zero-row/low-row highlights, prediction preview, and downloads;
- single article run: rules-only extraction, corrected PDF-stem evaluation,
  predictions, validation errors, field metrics, evidence, and provenance;
- full dataset run: explicit-confirmation wrapper around
  `scripts/run_benzimidazoles_full.py --llm-mode never`.
