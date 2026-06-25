from __future__ import annotations

from pathlib import Path

from pdf_extraction.image_extractor import ImageExtractionConfig
from pdf_extraction.models import ExtractedImageAsset, SourceProvenance, stable_pdf_stem


class PyMuPDFImageExtractor:
    method_name = "pymupdf.image_extraction"

    def extract(
        self,
        pdf_path: Path,
        output_dir: Path,
        config: ImageExtractionConfig | None = None,
    ) -> list[ExtractedImageAsset]:
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("PyMuPDF is required for image extraction: pip install pymupdf") from exc

        config = config or ImageExtractionConfig()
        output_dir.mkdir(parents=True, exist_ok=True)
        assets: list[ExtractedImageAsset] = []

        with fitz.open(pdf_path) as document:
            for page_index, page in enumerate(document, start=1):
                if config.save_page_renders:
                    render_path = output_dir / f"{stable_pdf_stem(pdf_path)}_p{page_index:03d}.png"
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(config.render_zoom, config.render_zoom), alpha=False)
                    pixmap.save(render_path)
                    assets.append(
                        ExtractedImageAsset(
                            image_id=f"p{page_index}_render",
                            path=str(render_path),
                            width=pixmap.width,
                            height=pixmap.height,
                            source=SourceProvenance(
                                source_file=pdf_path.name,
                                page=page_index,
                                figure_id=f"p{page_index}_render",
                                extraction_method="pymupdf.page_render",
                                confidence=0.85,
                            ),
                        )
                    )

                if not config.save_embedded_images:
                    continue

                for image_index, image_info in enumerate(page.get_images(full=True), start=1):
                    xref = image_info[0]
                    extracted = document.extract_image(xref)
                    image_bytes = extracted["image"]
                    extension = extracted.get("ext", "png")
                    width = extracted.get("width")
                    height = extracted.get("height")
                    if width and width < config.min_width:
                        continue
                    if height and height < config.min_height:
                        continue
                    image_id = f"p{page_index}_img{image_index}"
                    image_path = output_dir / f"{stable_pdf_stem(pdf_path)}_{image_id}.{extension}"
                    image_path.write_bytes(image_bytes)
                    assets.append(
                        ExtractedImageAsset(
                            image_id=image_id,
                            path=str(image_path),
                            width=width,
                            height=height,
                            source=SourceProvenance(
                                source_file=pdf_path.name,
                                page=page_index,
                                figure_id=image_id,
                                extraction_method=self.method_name,
                                confidence=0.8,
                            ),
                        )
                    )

        return assets
