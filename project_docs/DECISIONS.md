# Decisions

## 2026-06-25: Start With Local Lexical RAG

Decision: use a local JSONL index and BM25-style lexical retrieval before adding embeddings or a vector database.

Reason:

- The project already has useful Markdown notes.
- Local retrieval works offline and is easy to test.
- Provenance and collection boundaries matter more than semantic search quality at this stage.
- The interface can later be backed by embeddings without changing the project workflow.

## 2026-06-25: Keep Collections Separate

Decision: keep `project_docs`, `methodology_notes`, `code_examples`, and `molecule_facts` as separate logical collections.

Reason:

- Architecture decisions should not be mixed with factual molecule data.
- Method notes should guide implementation choices.
- Code examples should be retrieved as implementation patterns.
- Molecule facts should be queried only when factual chemical data is needed.

## 2026-06-25: PDF Parser Comes After RAG

Decision: do not start with a complex multi-agent system or a hardcoded PDF parser.

Reason:

- The immediate goal is one reusable workflow: scientific PDF to structured raw records with source references.
- RAG should first make project context and methodology retrievable.
- Agents become useful after the extraction/normalization/validation stages exist.

## 2026-06-25: One RAG Core, Multiple Collections

Decision: keep one `rag_core` package and represent different knowledge sources as logical collections, not as separate RAG systems.

Reason:

- `project_docs`, `methodology_notes`, `code_examples`, and `molecule_facts` share the same retrieval contract: source path, collection, heading, line range, score, and matched terms.
- A single retrieval layer prevents duplicated indexing, duplicated CLI commands, and conflicting rules.
- Lexical retrieval should work across all collections.
- Vector retrieval is optional and can be enabled per collection, starting with `methodology_notes` and later extending to `molecule_facts`.
- The project should spend complexity budget on the PDF extraction workflow first, not on multiple RAG implementations.
