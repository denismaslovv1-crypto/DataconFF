import unittest
from pathlib import Path

from pdf_extraction.pipeline import PROJECT_ROOT, resolve_project_path


class PdfPipelinePathTest(unittest.TestCase):
    def test_relative_paths_resolve_from_project_root(self) -> None:
        self.assertEqual(resolve_project_path("data/pdf_raw"), PROJECT_ROOT / "data" / "pdf_raw")

    def test_absolute_paths_are_preserved(self) -> None:
        path = Path("C:/tmp/example.pdf")
        self.assertEqual(resolve_project_path(path), path)


if __name__ == "__main__":
    unittest.main()
