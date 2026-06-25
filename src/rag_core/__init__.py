"""Local RAG memory layer for project notes and examples."""

from rag_core.index import build_index
from rag_core.retriever import RagRetriever

__all__ = ["RagRetriever", "build_index"]

