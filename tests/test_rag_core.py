from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rag_core.index import build_index
from rag_core.retriever import RagRetriever


class RagCoreTest(unittest.TestCase):
    def test_build_and_query_markdown_notes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            notes = root / "methodology_notes"
            docs = root / "project_docs"
            examples = root / "code_examples"
            facts = root / "molecule_facts"
            for directory in (notes, docs, examples, facts):
                directory.mkdir()

            (notes / "pdf.md").write_text(
                "# PDF extraction\n\nUse pdfplumber for table extraction and keep provenance.",
                encoding="utf-8",
            )
            (docs / "decisions.md").write_text("# Decisions\n\nRAG must return chunks.", encoding="utf-8")

            manifest = build_index(root, Path("rag_index"))
            self.assertGreaterEqual(manifest.chunk_count, 2)

            retriever = RagRetriever(root / "rag_index")
            results = retriever.search("table extraction provenance", top_k=1)

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].chunk.collection, "methodology_notes")
            self.assertIn("pdfplumber", results[0].chunk.text)


if __name__ == "__main__":
    unittest.main()

