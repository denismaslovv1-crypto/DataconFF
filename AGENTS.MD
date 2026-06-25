# AGENTS.md

## Project purpose

This project is a RAG-assisted system for chemical data extraction, dataset preparation, and future molecule selection workflows.

The system should not be treated as a simple chatbot over notes. RAG must be used as an engineering memory layer that retrieves only relevant fragments from project documentation, methodology notes, code examples, and chemical datasets.

## Current project structure

```text
project_docs/        # project architecture, roadmap, decisions, status
methodology_notes/   # Markdown notes about tools, methods, chemical data, RAG, extraction
molecule_facts/      # extracted chemical facts, datasets, normalized records
code_examples/       # draft and reusable parsers/extraction examples
```

Current known code example:

```text
code_examples/Datacon_web_extraction/
```

This contains a draft web parser for NIST Chemistry WebBook and PubChem.

Future examples may include PDF parsers, table extraction, graph extraction, image/OCR extraction, and molecule validation.

## Important constraint

Do not implement audio transcription in this project.

The project already has ready Markdown notes. Use existing `.md` files as RAG sources.

## Nearest goal

Build a universal PDF parser for chemical data extraction.

The parser must work as a reusable pipeline for different scientific PDFs, not as a hardcoded solution for one file.

It should support or prepare interfaces for:

```text
- text extraction
- table extraction
- image extraction
- chart/graph extraction
- OCR fallback
- chemical entity/property extraction
- normalization
- validation
- source provenance
```

Every extracted value should preserve its source:

```text
source file → page → section/table/figure → extraction method → confidence
```

## Long-term goal

Build a multi-agent system for:

```text
- chemical data collection
- PDF/web/API extraction
- dataset cleaning
- molecule/property normalization
- molecule selection by target properties
- validation of results
- final dataset export
```

Do not start with a complicated multi-agent system. First build:

```text
RAG core → PDF extraction MVP → chemical record extraction → dataset validation → agents
```

## RAG rules

Use separate logical knowledge collections:

```text
methodology_notes  # how to solve tasks
project_docs       # current architecture and decisions
code_examples      # reusable code patterns
molecule_facts     # factual chemical data and datasets
```

Before implementing a task:

1. Check `project_docs/` for architecture and current decisions.
2. Check `methodology_notes/` for relevant methods/tools.
3. Check `code_examples/` for similar existing code.
4. Check `molecule_facts/` only when factual molecule or dataset data is needed.

Do not load entire notes into context. Retrieve only relevant chunks.

## PDF parser design rules

The PDF parser should be modular.

Preferred future structure:

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

Do not hardcode PDF-specific page numbers, column names, molecule names, or table layouts in the core pipeline.

PDF-specific behavior should be handled through configuration or separate extractor modules.

## Data model rules

Use Pydantic models for structured extracted data.

Raw extraction, normalization, and validation must be separate stages.

Do not overwrite raw extracted data.

Chemical records should support optional fields such as:

```text
molecule_name
formula
molecular_weight
SMILES
canonical_SMILES
isomeric_SMILES
InChI
InChIKey
CAS
property_name
property_value
unit
source
confidence
validation_status
```

## Code style

Use Python.

Prefer:

```text
- pathlib
- type hints
- Pydantic
- modular functions/classes
- explicit errors
- logging
- CLI scripts
- tests for parsers and validators
```

Avoid:

```text
- monolithic scripts
- hardcoded absolute paths
- hardcoded logic for one PDF
- mixing extraction, normalization, and validation
- silently dropping source information
```

## Implementation priority

Current priority:

```text
1. Build RAG over existing Markdown notes and project docs.
2. Build universal PDF parser MVP.
3. Save raw extraction results with provenance.
4. Add chemical record extraction.
5. Add normalization and validation.
6. Add multi-agent workflow later.
```

## Definition of done for nearest task

The nearest task is done when the project has:

```text
- CLI command for parsing a PDF
- page-level text extraction
- table extraction interface or implementation
- structured JSON output
- Pydantic models for extracted records
- source provenance for extracted items
- basic tests or fixtures
- documentation explaining how to run the parser
```

## Core rule

First make one real workflow useful:

```text
Given a scientific PDF, extract chemical data into structured raw records with source references.
```

Then expand it into a RAG-assisted chemical dataset preparation and molecule selection system.


# Structure
AGENTS.md                         # short constant rules
project_docs/RAG_DESIGN.md        # detalization of RAG
project_docs/PDF_EXTRACTION_PLAN.md # PDF-parser pipleline
project_docs/ROADMAP.md           # Project stages
project_docs/DECISIONS.md        