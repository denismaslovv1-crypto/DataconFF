from __future__ import annotations

from pathlib import Path

import pdfplumber

from pdf_extraction.models import ExtractedTextBlock, SourceProvenance


class PdfTextExtractor:
    method_name = "pdfplumber.extract_text"

    def extract(self, pdf_path: Path) -> tuple[int, dict[str, str], list[ExtractedTextBlock]]:
        blocks: list[ExtractedTextBlock] = []
        with pdfplumber.open(pdf_path) as document:
            metadata = {str(key): str(value) for key, value in (document.metadata or {}).items()}
            page_count = len(document.pages)
            for page_number, page in enumerate(document.pages, start=1):
                text = page.extract_text() or ""
                confidence = 0.9 if text.strip() else 0.1
                blocks.append(
                    ExtractedTextBlock(
                        text=text,
                        source=SourceProvenance(
                            source_file=pdf_path.name,
                            page=page_number,
                            section=None,
                            extraction_method=self.method_name,
                            confidence=confidence,
                        ),
                    )
                )
        return page_count, metadata, blocks
