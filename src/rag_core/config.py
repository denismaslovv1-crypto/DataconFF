from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel, Field


class LlmConfig(BaseModel):
    provider: str = "openmodel"
    model: str = "deepseek-v4-flash"
    base_url: str = "https://api.openmodel.ai/v1"
    api_key_env: str = "OPENMODEL_API_KEY"


class EmbeddingsConfig(BaseModel):
    provider: str = "openai_compatible"
    model: str = "nvidia/llama-nemotron-embed-vl-1b-v2:free"
    base_url: str = "https://openrouter.ai/api/v1"
    api_key_env: str = "OPENROUTER_API_KEY"
    batch_size: int = Field(default=64, ge=1, le=2048)


class VectorStoreConfig(BaseModel):
    provider: str = "chroma"
    persist_dir: str = "rag_index/vector_chroma"
    collection_name: str = "methodology_notes"


class RagModelsConfig(BaseModel):
    llm: LlmConfig
    embeddings: EmbeddingsConfig
    vector_store: VectorStoreConfig


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_rag_models_config(project_root: Path, config_path: Path | None = None) -> RagModelsConfig:
    project_root = project_root.resolve()
    load_dotenv(project_root / ".env")
    path = config_path or project_root / "config" / "rag_models.json"
    if not path.is_absolute():
        path = project_root / path
    data = json.loads(path.read_text(encoding="utf-8"))
    return RagModelsConfig.model_validate(data)


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value or value == "replace_me":
        raise RuntimeError(
            f"Environment variable {name} is not set. Copy .env.example to .env and fill {name}."
        )
    return value
