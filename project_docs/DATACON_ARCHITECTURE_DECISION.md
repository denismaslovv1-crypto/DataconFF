# DataCon Architecture Decision

## Status

Accepted for the ChemX/DataCon hackathon implementation.

## Context

The repository already contains a local RAG layer, a modular PDF extraction MVP, parser examples, tests, and raw PDF parsing artifacts. The final DataCon task is not to build a generic PDF chatbot, but to produce benchmark-compatible chemical extraction outputs for ChemX and evaluate them by field-level Precision, Recall, F1, and Macro-F1.

The immediate goal is to obtain a positive benchmark result on one domain before expanding to additional domains.

## Core decision

Use a deterministic workflow/state machine instead of a free autonomous agent swarm.

```text
PDF
  -> parse text/tables/images
  -> build evidence chunks
  -> domain extraction
  -> normalization
  -> validation
  -> ChemX-compatible CSV/JSON export
  -> evaluation
  -> minimal web UI
```

Agents/tools may exist, but they must be narrow executors inside this workflow. They should not freely decide the whole process.

## Primary domain

Start with `Benzimidazoles`.

Reasons:

- It belongs to the small molecule track.
- Its single-agent Macro-F1 baseline is low enough to be beatable.
- The useful fields are mostly table/text extraction fields: `compound_id`, `target_type`, `target_relation`, `target_value`, `target_units`, `bacteria`.
- `smiles` is difficult and should be treated as low priority unless it is source-backed.

Fallback domains:

1. `Complexes`
2. `Co-crystals`

Do not attempt all ten ChemX domains before one end-to-end domain works.

## RAG decision

RAG remains an engineering memory and retrieval support layer. It is not the primary extraction engine.

Use RAG for:

- project decisions;
- methodology notes;
- extraction prompt examples;
- validation rules;
- reusable parser patterns.

Do not use RAG as:

```text
all PDFs -> vector database -> ask LLM to extract complete dataset
```

For source articles, use RAG-like retrieval only after deterministic parsing has created evidence chunks. The extraction workflow must still produce structured records and benchmark-compatible CSV.

## Extraction strategy

Use a hybrid extraction stack:

1. Reuse the existing PDF pipeline where possible.
2. Build evidence chunks from tables and text snippets around domain-specific keywords.
3. Run rule-based extraction first.
4. Run LLM extraction only on evidence chunks, not on the whole corpus.
5. Validate every record with Pydantic/domain schema.
6. Export only schema-compatible columns.

## Data integrity rules

Raw extraction, normalization, validation, and export are separate stages.

Raw values must not be overwritten by normalized values. Normalized records must point back to source evidence.

Minimum provenance target:

```text
source file -> page -> section/table/figure -> row -> extraction method -> confidence
```

LLMs are not trusted sources for numbers, units, SMILES, or provenance. If evidence is missing, use `NOT_DETECTED`.

## Chemical structure policy

Do not invent SMILES.

Allowed SMILES sources:

- article text/table;
- validated structure recognizer output;
- external API response with saved query/response;
- manual curation, if explicitly marked.

Generic scaffolds with `R`, `R1`, `R2`, `Ar`, or wildcard `*` are not identified molecules. Store them as unresolved scaffold evidence, not final molecule identity.

## Implementation target

Suggested package:

```text
src/datacon_workflow/
  state.py
  orchestrator.py
  domains/
    benzimidazoles.py
  extraction/
    evidence_builder.py
    rule_extractor.py
    llm_extractor.py
  normalization/
    units.py
    bacteria.py
  validation/
    schema_validator.py
  export/
    chemx_csv.py
  evaluation/
    chemx_eval.py
```

Minimal scripts:

```text
scripts/run_domain.py
scripts/evaluate_domain.py
```

Minimal UI:

```text
app.py or src/web_app/app.py
```

## Definition of success

A successful implementation has:

- a working Benzimidazoles pipeline;
- benchmark-compatible `predictions.csv`;
- `metrics.json` and field-level metrics;
- minimal Streamlit/Gradio UI;
- README commands that use the repository-local interpreter;
- no regression of existing tests.
