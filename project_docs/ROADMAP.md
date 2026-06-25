# Roadmap

## Stage 1: RAG Core

Status: in progress.

- Create logical collections for project docs, methodology notes, code examples, and molecule facts.
- Build a local index over existing notes.
- Return relevant chunks with file, heading, line range, and score.
- Use RAG before implementing parser and validation tasks.

## Stage 2: PDF Extraction MVP

Status: planned.

- Add `src/pdf_extraction/` modules.
- Implement PDF parse CLI.
- Extract page-level text with provenance.
- Add table extraction interface.
- Export structured raw JSON.
- Add tests/fixtures.

## Stage 3: Chemical Record Extraction

Status: planned.

- Detect molecule names, identifiers, formulas, properties, values, and units.
- Preserve raw records.
- Normalize into chemical record models.
- Link normalized records back to raw extraction provenance.

## Stage 4: Validation

Status: planned.

- Validate units and numeric ranges.
- Validate identifiers such as SMILES, InChI, InChIKey, CAS.
- Mark conflicts and uncertain records instead of deleting them.

## Stage 5: Agents

Status: later.

- Add multi-agent workflow only after one real PDF-to-record workflow is useful.
- Candidate agents: collector, extractor, normalizer, validator, exporter.

