import csv
import json
import tempfile
import unittest
from pathlib import Path

from pdf_extraction.crop_structure_importer import import_molscribe_crop
from pdf_extraction.exporters import write_document_json
from pdf_extraction.models import ParsedPdfDocument


class CropStructureImporterTest(unittest.TestCase):
    def test_import_molscribe_crop_updates_document_and_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "parsed"
            output_dir.mkdir()
            document = ParsedPdfDocument(source_file="paper.pdf", page_count=1)
            write_document_json(document, output_dir / "paper.raw.json")

            sidecar = root / "crop.png.json"
            sidecar.write_text(
                json.dumps(
                    {
                        "source_file": "paper.pdf",
                        "page": 1,
                        "crop_id": "paper_p001_fig1_mol001",
                        "image_path": "data/molecule_crops/paper_p001_fig1_mol001.png",
                        "bbox_points": {"x0": 10, "y0": 20, "x1": 30, "y1": 40},
                        "bbox_pixels": {"x0": 20, "y0": 40, "x1": 60, "y1": 80},
                        "image_width": 40,
                        "image_height": 40,
                        "extraction_method": "pymupdf.page_clip_render",
                        "confidence": 1.0,
                    }
                ),
                encoding="utf-8",
            )
            molscribe = root / "molscribe.json"
            molscribe.write_text(
                json.dumps(
                    {
                        "smiles": "CCO",
                        "canonical_SMILES": "CCO",
                        "isomeric_SMILES": "CCO",
                        "confidence": 0.91,
                        "molfile": "mol",
                    }
                ),
                encoding="utf-8",
            )

            updated = import_molscribe_crop(
                output_dir=output_dir,
                sidecar_path=sidecar,
                molscribe_json_path=molscribe,
                figure_id="Figure 1",
                caption="Figure 1. Lead compound.",
                compound_label="1",
                min_confidence=0.5,
            )

            self.assertEqual(len(updated.images), 1)
            self.assertEqual(len(updated.recognized_structures), 1)
            self.assertEqual(updated.chemical_records[0].record_type, "image_structure")
            self.assertEqual(updated.chemical_records[0].SMILES, "CCO")
            self.assertEqual(updated.chemical_records[0].source.figure_id, "Figure 1")

            with (output_dir / "chemical_records.csv").open(encoding="utf-8-sig", newline="") as file:
                row = next(csv.DictReader(file))

            self.assertEqual(row["record_type"], "image_structure")
            self.assertEqual(row["figure_id"], "Figure 1")
            self.assertEqual(row["compound_label"], "1")
            self.assertEqual(row["SMILES"], "CCO")
            self.assertEqual(row["crop_image_path"], "data/molecule_crops/paper_p001_fig1_mol001.png")
            self.assertIn('"x0":10.0', row["bbox_points"])


if __name__ == "__main__":
    unittest.main()
