from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

from pdf_extraction.models import ExtractedImageAsset


class ImageExtractionConfig(BaseModel):
    save_page_renders: bool = False
    save_embedded_images: bool = True
    min_width: int = 80
    min_height: int = 80
    render_zoom: float = 2.0


class ImageExtractor(Protocol):
    """Extract figure/image assets while preserving page provenance."""

    def extract(self, pdf_path: Path, output_dir: Path, config: ImageExtractionConfig | None = None) -> list[ExtractedImageAsset]:
        """Return image assets saved under output_dir."""


class NullImageExtractor:
    """No-op implementation for pipelines that do not process figures yet."""

    def extract(self, pdf_path: Path, output_dir: Path, config: ImageExtractionConfig | None = None) -> list[ExtractedImageAsset]:
        return []
