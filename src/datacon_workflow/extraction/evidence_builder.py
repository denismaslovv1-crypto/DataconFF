from __future__ import annotations

import re

from pydantic import BaseModel

from pdf_extraction.models import ParsedPdfDocument, SourceProvenance


INTERESTING = re.compile(r"\b(?:p?MIC|S\.?\s*aureus|Staph(?:ylococcus)?\.?\s*aureus|E\.?\s*coli|Escherichia\s+coli)\b", re.I)


class EvidenceChunk(BaseModel):
    text: str
    source: SourceProvenance
    row_id: str | None = None


def build_evidence_chunks(document: ParsedPdfDocument, context_characters: int = 300) -> list[EvidenceChunk]:
    """Select table rows and local text windows relevant to Benzimidazoles assays."""
    chunks: list[EvidenceChunk] = []
    for table in document.tables:
        for row_index, row in enumerate(table.rows):
            text = " | ".join(cell for cell in row if cell)
            if INTERESTING.search(text):
                chunks.append(EvidenceChunk(text=text, source=table.source, row_id=str(row_index)))
    for block in document.text_blocks:
        # Some publisher PDFs expose a visual table only as one text block.
        # Retain the complete block so a domain extractor can associate its
        # header, rows, footnotes, and column order without guessing across
        # unrelated snippets.
        if re.search(r"\b(?:MRSA\s*)?MIC\b|\b(?:MSSA|MRSA|ASSM|ASRM)\b", block.text, re.I):
            chunks.append(EvidenceChunk(text=block.text, source=block.source, row_id="table_like_text"))
            continue
        for match in INTERESTING.finditer(block.text):
            start = max(0, match.start() - context_characters)
            end = min(len(block.text), match.end() + context_characters)
            text = block.text[start:end].strip()
            if text:
                chunks.append(EvidenceChunk(text=text, source=block.source))
    return chunks
