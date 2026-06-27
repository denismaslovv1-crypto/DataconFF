from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class SourceProvenance(BaseModel):
    source_file: str
    page: int | None = None
    section: str | None = None
    table_id: str | None = None
    figure_id: str | None = None
    row_index: int | None = None
    extraction_method: str
    confidence: float = Field(ge=0.0, le=1.0)


class ExtractedTextBlock(BaseModel):
    text: str
    source: SourceProvenance


class ExtractedTable(BaseModel):
    table_id: str
    rows: list[list[str]]
    source: SourceProvenance


class ParsedPdfDocument(BaseModel):
    source_file: str
    page_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    text_blocks: list[ExtractedTextBlock] = Field(default_factory=list)
    tables: list[ExtractedTable] = Field(default_factory=list)


def stable_pdf_stem(pdf_path: Path) -> str:
    return pdf_path.stem.replace(" ", "_")

