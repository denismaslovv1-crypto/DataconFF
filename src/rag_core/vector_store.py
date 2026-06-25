from __future__ import annotations

from pathlib import Path
from typing import Any

from rag_core.models import RagChunk


def chunk_metadata(chunk: RagChunk) -> dict[str, str | int | float | bool]:
    source = chunk.source
    return {
        "collection": chunk.collection,
        "path": source.path,
        "title": source.title or "",
        "heading": source.heading or "",
        "line_start": source.line_start,
        "line_end": source.line_end,
    }


class ChromaVectorStore:
    def __init__(
        self,
        persist_dir: Path,
        collection_name: str,
        reset_collection: bool = False,
    ) -> None:
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError(
                "The chromadb package is required for vector storage. "
                "Install vector dependencies first: pip install -e .[vector]"
            ) from exc

        persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(persist_dir))
        if reset_collection:
            try:
                self.client.delete_collection(collection_name)
            except Exception:
                pass
        self.collection = self.client.get_or_create_collection(name=collection_name)

    def upsert(self, chunks: list[RagChunk], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        if not chunks:
            return

        self.collection.upsert(
            ids=[chunk.id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            metadatas=[chunk_metadata(chunk) for chunk in chunks],
            embeddings=embeddings,
        )

    def query(self, embedding: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        result = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        rows: list[dict[str, Any]] = []
        for index, chunk_id in enumerate(ids):
            rows.append(
                {
                    "id": chunk_id,
                    "document": documents[index],
                    "metadata": metadatas[index],
                    "distance": distances[index],
                }
            )
        return rows

