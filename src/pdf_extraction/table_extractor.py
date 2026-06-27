from __future__ import annotations

from pathlib import Path

from pdf_extraction.models import ExtractedTable, SourceProvenance


class PdfTableExtractor:
    method_name = "pdfplumber.extract_tables"

    def extract(self, pdf_path: Path) -> list[ExtractedTable]:
        import pdfplumber

        tables: list[ExtractedTable] = []
        with pdfplumber.open(pdf_path) as document:
            for page_number, page in enumerate(document.pages, start=1):
                for table_number, table in enumerate(page.extract_tables() or [], start=1):
                    rows = [
                        [self._clean_cell(cell) for cell in row]
                        for row in table
                        if row and any(self._clean_cell(cell) for cell in row)
                    ]
                    if not rows:
                        continue
                    table_id = f"p{page_number}_t{table_number}"
                    tables.append(
                        ExtractedTable(
                            table_id=table_id,
                            rows=rows,
                            source=SourceProvenance(
                                source_file=pdf_path.name,
                                page=page_number,
                                table_id=table_id,
                                extraction_method=self.method_name,
                                confidence=0.75,
                            ),
                        )
                    )
        return tables

    @staticmethod
    def _clean_cell(value: object) -> str:
        if value is None:
            return ""
        lines = [" ".join(line.split()) for line in str(value).splitlines()]
        return "\n".join(line for line in lines if line)
