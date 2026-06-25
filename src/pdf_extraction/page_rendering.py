from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pdf_extraction.models import stable_pdf_stem


@dataclass(frozen=True)
class PageRenderInfo:
    source_file: str
    page: int
    pdf_width: float
    pdf_height: float
    image_width: int
    image_height: int
    render_zoom: float
    image_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "page": self.page,
            "pdf_width": self.pdf_width,
            "pdf_height": self.pdf_height,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "render_zoom": self.render_zoom,
            "image_path": self.image_path,
        }


@dataclass(frozen=True)
class CropInfo:
    source_file: str
    page: int
    crop_id: str
    image_path: str
    render_zoom: float
    bbox_points: tuple[float, float, float, float]
    bbox_pixels: tuple[int, int, int, int]
    image_width: int
    image_height: int
    extraction_method: str = "pymupdf.page_clip_render"
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "page": self.page,
            "crop_id": self.crop_id,
            "image_path": self.image_path,
            "render_zoom": self.render_zoom,
            "bbox_points": _bbox_dict(self.bbox_points),
            "bbox_pixels": _bbox_dict(self.bbox_pixels),
            "image_width": self.image_width,
            "image_height": self.image_height,
            "extraction_method": self.extraction_method,
            "confidence": self.confidence,
        }


def render_pdf_pages(
    pdf_path: Path,
    output_dir: Path,
    pages: list[int] | None = None,
    zoom: float = 2.0,
) -> list[PageRenderInfo]:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required: pip install pymupdf") from exc

    if hasattr(fitz, "TOOLS"):
        fitz.TOOLS.mupdf_display_errors(False)

    output_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[PageRenderInfo] = []
    requested_pages = set(pages or [])

    with fitz.open(pdf_path) as document:
        for page_index, page in enumerate(document, start=1):
            if requested_pages and page_index not in requested_pages:
                continue
            image_path = output_dir / f"{stable_pdf_stem(pdf_path)}_p{page_index:03d}.png"
            pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            pixmap.save(image_path)
            rendered.append(
                PageRenderInfo(
                    source_file=pdf_path.name,
                    page=page_index,
                    pdf_width=float(page.rect.width),
                    pdf_height=float(page.rect.height),
                    image_width=int(pixmap.width),
                    image_height=int(pixmap.height),
                    render_zoom=zoom,
                    image_path=str(image_path),
                )
            )

    return rendered


def crop_pdf_region(
    pdf_path: Path,
    output_path: Path,
    page_number: int,
    bbox: tuple[float, float, float, float],
    bbox_units: str = "pixels",
    zoom: float = 2.0,
    crop_id: str | None = None,
) -> CropInfo:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required: pip install pymupdf") from exc

    if hasattr(fitz, "TOOLS"):
        fitz.TOOLS.mupdf_display_errors(False)

    if page_number < 1:
        raise ValueError("page_number is 1-based and must be >= 1")
    if bbox_units not in {"pixels", "points"}:
        raise ValueError("bbox_units must be 'pixels' or 'points'")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(pdf_path) as document:
        if page_number > len(document):
            raise ValueError(f"PDF has {len(document)} pages; requested page {page_number}")
        page = document[page_number - 1]
        bbox_points = _pixels_to_points(bbox, zoom) if bbox_units == "pixels" else bbox
        clip = fitz.Rect(*bbox_points) & page.rect
        if clip.is_empty or clip.width <= 0 or clip.height <= 0:
            raise ValueError(f"Crop bbox does not overlap page {page_number}: {bbox}")
        pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, alpha=False)
        pixmap.save(output_path)

    clipped_bbox = (float(clip.x0), float(clip.y0), float(clip.x1), float(clip.y1))
    pixel_bbox = _points_to_pixels(clipped_bbox, zoom)
    return CropInfo(
        source_file=pdf_path.name,
        page=page_number,
        crop_id=crop_id or output_path.stem,
        image_path=str(output_path),
        render_zoom=zoom,
        bbox_points=clipped_bbox,
        bbox_pixels=pixel_bbox,
        image_width=int(pixmap.width),
        image_height=int(pixmap.height),
    )


def write_manifest(items: list[PageRenderInfo] | list[CropInfo], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([item.to_dict() for item in items], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_sidecar(item: CropInfo, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(item.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def parse_bbox(value: str) -> tuple[float, float, float, float]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must have four comma-separated numbers: x0,y0,x1,y1")
    x0, y0, x1, y1 = (float(part) for part in parts)
    if x1 <= x0 or y1 <= y0:
        raise ValueError("bbox must satisfy x1 > x0 and y1 > y0")
    return x0, y0, x1, y1


def parse_pages(value: str | None) -> list[int] | None:
    if not value:
        return None
    pages: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if end < start:
                raise ValueError(f"Invalid page range: {part}")
            pages.extend(range(start, end + 1))
        else:
            pages.append(int(part))
    if any(page < 1 for page in pages):
        raise ValueError("Pages are 1-based and must be >= 1")
    return sorted(set(pages))


def _pixels_to_points(bbox: tuple[float, float, float, float], zoom: float) -> tuple[float, float, float, float]:
    return tuple(value / zoom for value in bbox)  # type: ignore[return-value]


def _points_to_pixels(bbox: tuple[float, float, float, float], zoom: float) -> tuple[int, int, int, int]:
    return tuple(round(value * zoom) for value in bbox)  # type: ignore[return-value]


def _bbox_dict(bbox: tuple[float, float, float, float] | tuple[int, int, int, int]) -> dict[str, float | int]:
    return {"x0": bbox[0], "y0": bbox[1], "x1": bbox[2], "y1": bbox[3]}
