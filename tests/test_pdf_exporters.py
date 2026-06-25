import csv
import tempfile
import unittest
from pathlib import Path

from pdf_extraction.exporters import write_compound_labels_csv, write_records_csv
from pdf_extraction.models import RawChemicalRecord, SourceProvenance


class PdfExporterTest(unittest.TestCase):
    def test_records_csv_marks_unresolved_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "records.csv"
            write_records_csv([self._record()], output_path)

            with output_path.open(encoding="utf-8-sig", newline="") as file:
                row = next(csv.DictReader(file))

            self.assertEqual(row["structure_resolution_status"], "unresolved_label")
            self.assertEqual(row["needs_structure_image_mapping"], "True")

    def test_compound_labels_csv_groups_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "labels.csv"
            write_compound_labels_csv([self._record(property_name="Ki"), self._record(property_name="IC50")], output_path)

            with output_path.open(encoding="utf-8-sig", newline="") as file:
                rows = list(csv.DictReader(file))

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["compound_label"], "4d")
            self.assertEqual(rows[0]["record_count"], "2")
            self.assertEqual(rows[0]["needs_structure_image_mapping"], "True")

    def test_wildcard_smiles_is_not_resolved_structure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "records.csv"
            record = self._record()
            record.SMILES = "*C(=O)C"
            record.is_generic_structure = True
            record.generic_structure_reason = "wildcard_atom_in_smiles"
            write_records_csv([record], output_path)

            with output_path.open(encoding="utf-8-sig", newline="") as file:
                row = next(csv.DictReader(file))

            self.assertEqual(row["structure_resolution_status"], "unresolved_label")
            self.assertEqual(row["is_generic_structure"], "True")
            self.assertEqual(row["generic_structure_reason"], "wildcard_atom_in_smiles")

    def _record(self, property_name: str = "Ki") -> RawChemicalRecord:
        return RawChemicalRecord(
            record_id=f"r_{property_name}",
            record_type="table_property",
            compound_label="4d",
            property_name=property_name,
            property_value="12",
            unit="nM",
            raw_value="12",
            source=SourceProvenance(
                source_file="paper.pdf",
                page=3,
                extraction_method="test",
                confidence=1.0,
            ),
            confidence=0.5,
        )


if __name__ == "__main__":
    unittest.main()
