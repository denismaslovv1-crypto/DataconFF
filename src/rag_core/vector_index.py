from __future__ import annotations

from pathlib import Path

from rag_core.config import load_rag_models_config
from rag_core.embeddings import create_embedding_provider
from rag_core.index import build_index, load_chunks
from rag_core.models import RagChunk
from rag_core.vector_store import ChromaVectorStore


def batched(items: list[RagChunk], size: int) -> list[list[RagChunk]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def build_vector_index(
    project_root: Path,
    index_dir: Path,
    config_path: Path | None = None,
    collection: str = "methodology_notes",
    rebuild_text_index: bool = True,
    reset_vector_collection: bool = True,
) -> int:
    project_root = project_root.resolve()
    if rebuild_text_index:
        build_index(project_root=project_root, index_dir=index_dir)

    config = load_rag_models_config(project_root, config_path)
    chunks = [chunk for chunk in load_chunks(project_root / index_dir) if chunk.collection == collection]
    provider = create_embedding_provider(config.embeddings)
    store = ChromaVectorStore(
        persist_dir=project_root / config.vector_store.persist_dir,
        collection_name=collection,
        reset_collection=reset_vector_collection,
    )

    indexed = 0
    for batch in batched(chunks, config.embeddings.batch_size):
        embeddings = provider.embed_documents([chunk.text for chunk in batch])
        store.upsert(batch, embeddings)
        indexed += len(batch)
        print(f"Indexed {indexed}/{len(chunks)} chunks")
    return indexed


def query_vector_index(
    project_root: Path,
    query: str,
    config_path: Path | None = None,
    collection: str = "methodology_notes",
    top_k: int = 5,
) -> list[dict]:
    project_root = project_root.resolve()
    config = load_rag_models_config(project_root, config_path)
    provider = create_embedding_provider(config.embeddings)
    store = ChromaVectorStore(
        persist_dir=project_root / config.vector_store.persist_dir,
        collection_name=collection,
        reset_collection=False,
    )
    embedding = provider.embed_query(query)
    return store.query(embedding, top_k=top_k)
