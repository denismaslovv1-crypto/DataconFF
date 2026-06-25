from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field

from pdf_extraction.command_tools import CommandToolConfig, load_json_file, render_command, run_command
from pdf_extraction.models import BoundingBox, ExtractedImageAsset, SourceProvenance


class StructureDetectionConfig(BaseModel):
    tool: CommandToolConfig | None = None
    manifest_path: str = "{output_dir}/{image_id}_detections.json"
    min_confidence: float = 0.5


class StructureDetector(Protocol):
    """Detect molecule/reaction crops before structure recognition."""

    def detect(
        self,
        images: list[ExtractedImageAsset],
        output_dir: Path,
        config: StructureDetectionConfig | None = None,
    ) -> list[ExtractedImageAsset]:
        """Return detected structure crops or original images if no cropper is configured."""


class NullStructureDetector:
    def detect(
        self,
        images: list[ExtractedImageAsset],
        output_dir: Path,
        config: StructureDetectionConfig | None = None,
    ) -> list[ExtractedImageAsset]:
        return images


class ExternalCommandStructureDetector:
    """Runs a YOLO-style detector command that writes a JSON detection manifest.

    The manifest should be a list of objects. Supported keys:
    `image_path` or `path`, `image_id`, `bbox`, `confidence`, `page`.
    """

    def __init__(self, config: StructureDetectionConfig) -> None:
        self.config = config

    def detect(
        self,
        images: list[ExtractedImageAsset],
        output_dir: Path,
        config: StructureDetectionConfig | None = None,
    ) -> list[ExtractedImageAsset]:
        config = config or self.config
        if not config.tool or not config.tool.enabled:
            return images

        output_dir.mkdir(parents=True, exist_ok=True)
        detected: list[ExtractedImageAsset] = []
        for image in images:
            manifest_path = Path(
                config.manifest_path.format(
                    output_dir=str(output_dir),
                    image_id=image.image_id,
                    image_path=image.path,
                )
            )
            command = render_command(
                config.tool.command,
                {
                    "image_path": image.path,
                    "image_id": image.image_id,
                    "output_dir": str(output_dir),
                    "manifest_path": str(manifest_path),
                },
            )
            run_command(command, config.tool.timeout_seconds)
            if not manifest_path.exists():
                continue
            detected.extend(self._assets_from_manifest(load_json_file(manifest_path), image, config.min_confidence))
        return detected or images

    def _assets_from_manifest(
        self,
        payload: Any,
        parent_image: ExtractedImageAsset,
        min_confidence: float,
    ) -> list[ExtractedImageAsset]:
        rows = payload if isinstance(payload, list) else payload.get("detections", []) if isinstance(payload, dict) else []
        assets: list[ExtractedImageAsset] = []
        for index, item in enumerate(rows, start=1):
            if not isinstance(item, dict):
                continue
            confidence = float(item.get("confidence", parent_image.source.confidence))
            if confidence < min_confidence:
                continue
            path = item.get("image_path") or item.get("path") or parent_image.path
            image_id = item.get("image_id") or f"{parent_image.image_id}_det{index}"
            bbox = _bbox_from_value(item.get("bbox"))
            assets.append(
                ExtractedImageAsset(
                    image_id=image_id,
                    path=str(path),
                    compound_label=item.get("compound_label") or item.get("label"),
                    width=item.get("width"),
                    height=item.get("height"),
                    bbox=bbox,
                    caption=parent_image.caption,
                    source=SourceProvenance(
                        source_file=parent_image.source.source_file,
                        page=item.get("page") or parent_image.source.page,
                        figure_id=image_id,
                        extraction_method="external_yolo_detection",
                        confidence=confidence,
                    ),
                )
            )
        return assets


def _bbox_from_value(value: Any) -> BoundingBox | None:
    if isinstance(value, dict):
        return BoundingBox(**value)
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return BoundingBox(x0=value[0], y0=value[1], x1=value[2], y1=value[3])
    return None
