from __future__ import annotations

import json
from pathlib import Path

from pdf_extraction.models import ParsedPdfDocument


def write_document_json(document: ParsedPdfDocument, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(document.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

