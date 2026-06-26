# DataCon'26 ChemX final task brief

## Goal

Build a reproducible system for automated chemical information extraction from scientific PDF articles.

The system must extract structured chemical records from literature and compare its quality against the ChemX single-agent baseline.

## Benchmark

ChemX is a benchmark collection for chemical information extraction from scientific publications. It contains 10 datasets across two directions:

```text
small molecules
nanomaterials
```

Each dataset row corresponds to one extracted chemical object, material, compound, or experimental measurement from a scientific article.

## Required pipeline

The expected solution follows this high-level pipeline:

```text
Scientific PDF
  -> preprocessing: parse PDF, extract text/tables/images
  -> extraction: LLM, rules, RAG support, multi-agent workflow, or hybrid method
  -> evaluation: Precision / Recall / F1 / Macro-F1
  -> web interface: upload PDF and view extracted records
```

Technology choices are open, but the final result must be reproducible.

## Main target

The minimum successful result is to exceed the published ChemX single-agent Macro-F1 on at least one domain.

Primary implementation target for this project:

```text
Benzimidazoles
```

Reason:

```text
- small-molecule domain
- relatively low single-agent Macro-F1 baseline
- table-heavy MIC/pMIC extraction task
- compatible with the existing PDF extraction MVP
```

Fallback domains after the primary workflow works:

```text
Complexes
Co-crystals
```

## Benzimidazoles schema

The benchmark-compatible prediction CSV for the Benzimidazoles domain must use the expected target columns:

```text
compound_id
smiles
target_type
target_relation
target_value
target_units
bacteria
```

Priority order:

```text
1. compound_id
2. target_type
3. target_relation
4. target_value
5. target_units
6. bacteria
7. smiles
```

`smiles` is low priority unless source-backed. Do not invent molecular structures.

## Baseline to beat

Published single-agent Macro-F1 values from the task statement:

| Domain | Direction | Single-agent Macro-F1 |
|---|---|---:|
| Benzimidazoles | Small molecules | 0.217 |
| Oxazolidinones | Small molecules | 0.491 |
| Co-crystals | Small molecules | 0.296 |
| Complexes | Small molecules | 0.290 |
| Nanozymes | Nanomaterials | 0.164 |
| Synergy | Nanomaterials | 0.080 |
| Nanomag | Nanomaterials | 0.034 |
| Cytotox | Nanomaterials | 0.182 |
| SelTox | Nanomaterials | 0.045 |

## Evaluation

ChemX evaluates extraction quality by field:

```text
Precision
Recall
F1
Macro-F1
```

Macro-F1 is the primary comparison metric.

The prediction CSV must match the selected domain schema. Extra, missing, renamed, or reordered columns can break evaluation or make metrics unreliable.

## Required deliverables

Minimum deliverables:

```text
- extraction system
- benchmark-compatible CSV output
- final Macro-F1 metrics on selected ChemX domain(s)
- web UI for PDF upload and extracted table display
- reproducible repository with README and pinned dependencies
```

Scoring categories:

```text
- extraction quality: 40
- web interface: 20
- code and README quality: 20
- presentation and answers: 20
```

Bonus:

```text
- additional domains beyond the first
- solution working on both small molecules and nanomaterials
```

## Recommended project strategy

Do not build a universal chemistry agent first.

Build a deterministic, observable extraction workflow for one domain:

```text
PDF
  -> parse text/tables/images
  -> build evidence chunks
  -> extract Benzimidazoles records
  -> normalize fields
  -> validate schema
  -> export ChemX-compatible CSV
  -> evaluate Macro-F1 and field-level F1
  -> display in Streamlit/Gradio UI
```

RAG may be used for project memory and retrieving relevant evidence chunks, but the benchmark output should be produced by a controlled extraction pipeline, not by asking a vector database to generate the dataset.

## Important constraints

```text
- Do not treat LLM output as ground truth.
- Do not invent numbers, units, SMILES, or provenance.
- Use NOT_DETECTED when evidence is absent.
- Keep raw extraction, normalization, validation, and export separate.
- Preserve source evidence whenever possible.
- Start with one domain, then expand only after stable positive metrics.
```
