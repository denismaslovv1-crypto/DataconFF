import unittest

from pdf_extraction.models import RawChemicalRecord, RecognizedStructure, SourceProvenance
from pdf_extraction.structure_mapper import apply_structure_mappings, structures_to_records


class StructureMapperTest(unittest.TestCase):
    def test_apply_structure_mapping_by_compound_label(self) -> None:
        record = RawChemicalRecord(
            record_id="r1",
            record_type="table_property",
            compound_label="4d",
            property_name="Ki",
            property_value="12",
            raw_value="12",
            source=self._source(),
            confidence=0.5,
        )
        structure = RecognizedStructure(
            structure_id="s1",
            image_id="img1",
            compound_label="4d",
            smiles_raw="CCO",
            recognizer="molscribe",
            source=self._source(),
            confidence=0.8,
        )

        mapped = apply_structure_mappings([record], [structure])

        self.assertEqual(mapped[0].SMILES, "CCO")
        self.assertEqual(mapped[0].structure_id, "s1")
        self.assertEqual(mapped[0].image_id, "img1")
        self.assertEqual(mapped[0].validation_status, "structure_mapped_unvalidated")

    def test_structures_to_records_exports_image_structure_rows(self) -> None:
        structure = RecognizedStructure(
            structure_id="s1",
            image_id="img1",
            compound_label="4d",
            smiles_raw="CCO",
            recognizer="molscribe",
            source=self._source(),
            confidence=0.8,
        )

        records = structures_to_records("paper.pdf", [structure])

        self.assertEqual(records[0].record_type, "image_structure")
        self.assertEqual(records[0].SMILES, "CCO")
        self.assertEqual(records[0].compound_label, "4d")

    def _source(self) -> SourceProvenance:
        return SourceProvenance(
            source_file="paper.pdf",
            page=1,
            figure_id="fig1",
            extraction_method="test",
            confidence=1.0,
        )


if __name__ == "__main__":
    unittest.main()
