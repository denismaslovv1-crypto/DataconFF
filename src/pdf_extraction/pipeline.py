from __future__ import annotations

from pathlib import Path
from typing import Any

from pdf_extraction.models import ParsedPdfDocument
from pdf_extraction.table_extractor import PdfTableExtractor
from pdf_extraction.text_extractor import PdfTextExtractor


class PdfExtractionPipeline:
    def __init__(self, text_extractor: Any | None = None, table_extractor: Any | None = None) -> None:
        self.text_extractor = text_extractor or PdfTextExtractor()
        self.table_extractor = table_extractor or PdfTableExtractor()

    def parse_pdf(self, pdf_path: Path, output_dir: Path | None = None) -> ParsedPdfDocument:
        del output_dir
        page_count, metadata, text_blocks = self.text_extractor.extract(pdf_path)
        tables = self.table_extractor.extract(pdf_path)
        return ParsedPdfDocument(
            source_file=pdf_path.name,
            page_count=page_count,
            metadata=metadata,
            text_blocks=text_blocks,
            tables=tables,
        )


def parse_pdf(pdf_path: Path, output_dir: Path | None = None) -> ParsedPdfDocument:
    return PdfExtractionPipeline().parse_pdf(pdf_path, output_dir=output_dir)

