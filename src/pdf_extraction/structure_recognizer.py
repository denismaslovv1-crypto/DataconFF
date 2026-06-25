from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

from pdf_extraction.models import ExtractedImageAsset, RecognizedStructure


class StructureRecognitionConfig(BaseModel):
    detector: str = "manual_or_yolo"
    recognizer: str = "molscribe_or_osra"
    min_confidence: float = 0.5


class StructureRecognizer(Protocol):
    """Convert molecule structure images into raw SMILES/MOL candidates."""

    def recognize(
        self,
        images: list[ExtractedImageAsset],
        config: StructureRecognitionConfig | None = None,
    ) -> list[RecognizedStructure]:
        """Return raw structure candidates with image provenance."""


class ReactionRecognizer(Protocol):
    """Convert reaction scheme images into reaction-level candidates."""

    def recognize_reactions(
        self,
        images: list[ExtractedImageAsset],
        config: StructureRecognitionConfig | None = None,
    ) -> list[RecognizedStructure]:
        """Return raw reaction candidates, for example from RxnScribe."""


class NullStructureRecognizer:
    """No-op recognizer used until YOLO/MolScribe/OSRA/RxnScribe adapters exist."""

    def recognize(
        self,
        images: list[ExtractedImageAsset],
        config: StructureRecognitionConfig | None = None,
    ) -> list[RecognizedStructure]:
        return []

    def recognize_reactions(
        self,
        images: list[ExtractedImageAsset],
        config: StructureRecognitionConfig | None = None,
    ) -> list[RecognizedStructure]:
        return []
