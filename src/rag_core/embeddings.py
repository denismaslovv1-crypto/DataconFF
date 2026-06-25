from __future__ import annotations

import sys
from typing import Protocol

from rag_core.config import EmbeddingsConfig, require_env


class EmbeddingProvider(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[float]:
        ...


class OpenAICompatibleEmbeddingProvider:
    def __init__(self, config: EmbeddingsConfig) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "The openai package is required for API embeddings. "
                f"The selected Python interpreter is {sys.executable!r}. "
                "Install vector dependencies for that interpreter first: "
                f"{sys.executable} -m pip install -e .[vector]"
            ) from exc

        self.config = config
        self.client = OpenAI(
            api_key=require_env(config.api_key_env),
            base_url=config.base_url,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self.client.embeddings.create(
            input=texts,
            model=self.config.model,
            encoding_format="float",
        )
        return [item.embedding for item in response.data]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def create_embedding_provider(config: EmbeddingsConfig) -> EmbeddingProvider:
    if config.provider != "openai_compatible":
        raise ValueError(f"Unsupported embeddings provider: {config.provider}")
    return OpenAICompatibleEmbeddingProvider(config)
