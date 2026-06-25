from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RagSource(BaseModel):
    collection: str
    path: str
    title: str | None = None
    heading: str | None = None
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)


class RagChunk(BaseModel):
    id: str
    collection: str
    source: RagSource
    text: str
    char_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceFileRecord(BaseModel):
    collection: str
    path: str
    chunks: int
    char_count: int


class RagIndexManifest(BaseModel):
    built_at: datetime
    project_root: str
    chunk_count: int
    source_files: list[SourceFileRecord]
    collections: dict[str, str]


class SearchResult(BaseModel):
    chunk: RagChunk
    score: float
    matched_terms: list[str] = Field(default_factory=list)

