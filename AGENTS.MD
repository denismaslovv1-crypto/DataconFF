# AGENTS.md

## Project mission

This repository is for the DataCon/ChemX final task: automated chemical information extraction from scientific literature.

The project is not a generic PDF chatbot and not a note-taking RAG demo. The required result is a reproducible extraction workflow:

```text
scientific PDF
  -> parsed text / tables / images
  -> evidence-backed raw records
  -> normalized records
  -> validated ChemX-compatible CSV/JSON
  -> Precision / Recall / F1 / Macro-F1 evaluation
  -> minimal web UI for PDF upload and extracted table review
```

## Current benchmark target

Primary domain:

```text
Benzimidazoles
```

Reason: it is a small-molecule ChemX domain with a low single-agent baseline and a table-heavy structure suitable for the existing PDF extraction MVP.

Fallback domains, only after the primary path is working:

```text
Complexes
Co-crystals
```

Do not attempt to solve all ChemX domains before one domain works end-to-end.

## Main success criterion

Produce benchmark-compatible predictions for at least one ChemX domain and exceed the published single-agent Macro-F1 for that domain.

For Benzimidazoles, the benchmark CSV schema must contain exactly the expected target columns:

```text
compound_id
smiles
target_type
target_relation
target_value
target_units
bacteria
```

Prioritize these fields in this order:

```text
1. compound_id
2. target_type
3. target_relation
4. target_value
5. target_units
6. bacteria
7. smiles
```

Treat `smiles` as low priority unless it is source-backed. Never invent SMILES.

## Required project documents

Before major implementation work, read or query the relevant parts of:

```text
README.md
AGENTS.md
Datacon_preparation.md or project_docs/DATACON_PREPARATION.md
project_docs/DATACON_FINAL_TASK_BRIEF.md
project_docs/DATACON_EXECUTION_CHECKLIST.md
project_docs/DECISIONS.md
project_docs/RAG_DESIGN.md
project_docs/PDF_EXTRACTION_PLAN.md
```

Use RAG for targeted retrieval from project documentation and methodology notes. Do not load entire long notes into context.

## Repository-local Python policy

Use only the repository-local interpreter:

```powershell
.\.venv\Scripts\python.exe
```

Do not use:

```text
python
python3
py
system Python
Codex runtime
interpreters outside the repository
```

If the repository-local interpreter is missing, stop and report:

```text
- current working directory
- checked interpreter paths
- command that could not be run
- what the user should create or install
```

Do not silently install heavy dependencies. Ask before adding tools such as Docling, Marker, RDKit, Chroma, Qdrant, MolScribe, DECIMER, OSRA, YOLO, or OCR stacks unless they are already part of the project environment.

## Existing architecture to preserve

Reuse the current project structure:

```text
project_docs/        architecture, roadmap, decisions, benchmark task docs
methodology_notes/   notes about chemical data, PDF extraction, RAG, validation
molecule_facts/      factual molecule and dataset records
code_examples/       reusable extraction examples and parser drafts
src/rag_core/        local RAG indexing and retrieval layer
src/pdf_extraction/  PDF parser MVP and optional structure-recognition interfaces
rag_index/           generated local RAG/Chroma indexes
tests/               unit tests
```

Do not rewrite the project from scratch. Prefer small, testable additions.

## RAG rules

RAG is an engineering memory and retrieval support layer, not the main extraction engine.

Use RAG for:

```text
- project rules
- architecture decisions
- ChemX task details
- methodology notes
- prompt and parser examples
```

Do not use RAG as:

```text
PDF -> vector DB -> ask the LLM to extract the whole benchmark dataset
```

Scientific articles should be processed through the extraction pipeline:

```text
PDF -> parser -> text/tables/images -> evidence chunks -> extractor -> validator -> CSV
```

## Workflow architecture

Do not build a free autonomous agent swarm.

Use a deterministic workflow or state machine with narrow stages:

```text
Ingest
  -> Parse
  -> Evidence extraction
  -> Domain extraction
  -> Normalize
  -> Validate
  -> Export
  -> Evaluate
  -> Web UI
```

Agents or LLM calls may be used inside individual stages, but the orchestrator must remain observable and reproducible.

Recommended state object:

```text
pdf_path
parsed_document
evidence_chunks
raw_records
normalized_records
validation_errors
prediction_csv
metrics
```

## Data integrity rules

Raw extraction, normalization, validation, and export are separate stages.

Never overwrite raw extracted data with normalized values.

Every extracted value should preserve provenance when possible:

```text
source file -> page -> section/table/figure -> row -> extraction method -> confidence
```

If evidence is missing, use:

```text
NOT_DETECTED
```

Do not hide missing values as empty strings unless the ChemX evaluator explicitly requires that format.

## LLM rules

LLMs may help with:

```text
- planning
- interpreting table/caption context
- extracting JSON from evidence chunks
- resolving ambiguous local context
- preparing review packages
```

LLMs must not be treated as ground truth for:

```text
- numeric values
- units
- SMILES
- InChI / InChIKey
- DOI / source metadata
- provenance
```

Any LLM-produced record must be validated against schema and evidence.

LLM output for extraction must be JSON only. Reject or repair invalid JSON in a controlled way, then validate with Pydantic.

## Chemistry-specific rules

Do not invent chemical structures.

SMILES with wildcard `*`, R/R1/R2/Ar fragments, generic scaffolds, or unresolved substituent tables are not final molecule identities.

Mark unresolved generic structures explicitly and do not link them to a compound as an identified molecule unless substituents are source-backed.

Prefer source-backed identifiers from:

```text
- article text
- tables
- figures/captions
- supplementary materials
- saved external API response
- validated external recognizer output
```

## Benzimidazoles extraction rules

For the primary domain, extract every MIC or pMIC mention for benzimidazole antibiotics.

Each measurement should become a separate record.

Do not deduplicate during raw extraction. If the same measurement appears in different contexts, keep separate raw records and let validation/export decide.

Expected fields:

```text
compound_id      article-local compound identifier, e.g. 5a or Compound 3
smiles           full source-backed SMILES or NOT_DETECTED
target_type      MIC or pMIC
target_relation  =, <, or >; default to = only when the source shows no relation
target_value     numeric value or source-preserved range if evaluator supports it
target_units     units exactly or normalized to benchmark-compatible form
bacteria         organism name as reported or normalized alias
```

Useful aliases:

```text
S. aureus -> Staphylococcus aureus
E. coli -> Escherichia coli
```

## Evaluation rules

Evaluation is mandatory, not optional.

Save outputs under a stable path such as:

```text
outputs/benzimidazoles/predictions.csv
outputs/benzimidazoles/predictions.json
outputs/benzimidazoles/metrics.json
outputs/benzimidazoles/field_metrics.csv
```

Always inspect both:

```text
- Macro-F1
- field-level F1
```

A change is not successful just because the extraction looks plausible. It is successful only when metrics improve or the workflow becomes more reproducible without losing quality.

## Stable positive result rule

A task shows a stable positive result only when:

```text
- the workflow runs end-to-end from input PDF/data to benchmark-compatible CSV
- evaluation is reproducible from committed code/config
- tests pass or known failures are documented
- Macro-F1 exceeds the relevant single-agent baseline, or a clearly documented field-level improvement is achieved without lowering the current Macro-F1
```

When this happens, update:

```text
project_docs/DATACON_EXECUTION_CHECKLIST.md
README.md
reports/final_metrics.md or the current metrics report
```

## Web UI scope

A minimal UI is enough.

Use Streamlit or Gradio unless the repository already has another UI stack.

Required UI features:

```text
- upload/select PDF
- choose domain
- run extraction
- display extracted table
- show validation status and evidence when available
- download CSV/JSON
```

Do not spend time on complex styling before extraction and metrics work.

## Code style

Use Python.

Prefer:

```text
- pathlib
- type hints
- Pydantic
- small modules
- explicit errors
- logging
- CLI scripts
- tests
```

Avoid:

```text
- monolithic scripts
- hardcoded absolute paths
- hidden global state
- hardcoded page numbers or one-PDF logic in core modules
- mixing extraction, normalization, validation, and export
- silently dropping provenance
```

## Suggested new modules

When implementing the ChemX workflow, prefer additions like:

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

scripts/
  run_domain.py
  evaluate_domain.py

app.py
```

Adjust names to the existing repository style when needed.

## Testing

Run tests after meaningful changes:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Add focused tests for:

```text
- domain schema
- CSV column order
- relation parsing
- unit normalization
- bacteria alias normalization
- NOT_DETECTED handling
- exporter output
```

## Definition of done for the current phase

The current phase is done when the repository has:

```text
- documented ChemX task brief
- maintained execution checklist
- domain config/schema for Benzimidazoles
- deterministic extraction/evaluation command
- ChemX-compatible prediction CSV
- metrics report with Macro-F1 and field-level F1
- minimal web UI
- README commands using .\.venv\Scripts\python.exe
```
