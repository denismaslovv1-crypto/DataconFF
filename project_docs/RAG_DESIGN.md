# RAG Design

## Purpose

The RAG layer is the project memory system for chemical data extraction work. It should retrieve small, relevant fragments from project documentation, methodology notes, reusable examples, and molecule facts before implementation decisions are made.

It is not a generic chatbot over all files. The retriever must preserve collection boundaries and source provenance so later agents can explain why a method, parser, or validation rule was chosen.

## Collections

| Collection | Directory | Use |
| --- | --- | --- |
| `project_docs` | `project_docs/` | Architecture, roadmap, decisions, current status. |
| `methodology_notes` | `methodology_notes/` | Methods and tools for PDF, web, table, graph, OCR, chemistry, and validation tasks. |
| `code_examples` | `code_examples/` | Reusable parser patterns and extraction examples. |
| `molecule_facts` | `molecule_facts/` | Factual molecule records, datasets, and normalized facts. |

## Retrieval Contract

Every retrieved chunk must include:

```text
collection -> source file -> heading -> line range -> score -> matched terms
```

For future extracted chemical values, provenance must extend to:

```text
source file -> page -> section/table/figure -> extraction method -> confidence
```

## Current Implementation

The initial implementation is a local lexical RAG layer:

```text
Markdown/source files
  -> heading-aware chunking
  -> JSONL chunk index
  -> BM25-style local retriever
  -> top-k relevant chunks with provenance
```

This is intentionally lightweight. It works without network access and without a vector database, while leaving a clean interface for future embeddings and Qdrant/FAISS integration.

## Vector Extension

The project also has a prepared vector layer for selected collections. This is not a separate RAG system. It is an optional backend inside the same `rag_core` contract:

```text
chunks.jsonl
  -> filter by logical collection
  -> OpenAI-compatible embeddings provider
  -> Chroma persistent collection named after the logical collection
  -> vector-query top-k chunks
```

Default vector usage starts with `methodology_notes`, because method notes benefit most from semantic retrieval. Later, `molecule_facts` can get its own vector collection when factual chemical records become large enough.

Configuration lives in:

```text
config/rag_models.json
.env
```

Do not store API keys in code or committed config files. Keep keys in `.env`, using `.env.example` as the template.

DeepSeek is configured as the answer-generation LLM. For embeddings, use a provider/model that exposes an embeddings endpoint.

## Index Files

Generated files live in `rag_index/`:

```text
rag_index/chunks.jsonl
rag_index/manifest.json
```

`chunks.jsonl` stores chunk text and provenance. `manifest.json` stores build time, indexed collections, source files, and chunk counts.

## Usage

Build:

```powershell
scripts/rag.ps1 build
```

Query:

```powershell
scripts/rag.ps1 query "PDF table extraction provenance"
```

Build vector DB for methodology notes:

```powershell
scripts/vector.ps1 build
```

Query vector DB:

```powershell
scripts/vector.ps1 query "chemical normalization validation"
```

Build/query another logical collection when needed:

```powershell
scripts/vector.ps1 build -Collection molecule_facts
scripts/vector.ps1 query "aspirin canonical smiles" -Collection molecule_facts
```

For direct Python usage:

```powershell
python -m rag_core query "chemical normalization validation"
```

## Rules For Future Work

1. Query `project_docs` first for architecture and decisions.
2. Query `methodology_notes` for relevant methods and tool choices.
3. Query `code_examples` for reusable implementation patterns.
4. Query `molecule_facts` only when factual chemical or dataset data is needed.
5. Do not load entire notes into context when a query can retrieve targeted chunks.
6. Do not mix raw extraction, normalization, and validation in the same stage.
7. Do not create separate RAG systems for each source type; add logical collections and retrieval rules inside `rag_core`.
