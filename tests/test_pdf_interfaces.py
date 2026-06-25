import unittest
from pathlib import Path

from pdf_extraction.identifier_enricher import NullIdentifierEnricher
from pdf_extraction.image_extractor import NullImageExtractor
from pdf_extraction.models import RawChemicalRecord, SourceProvenance
from pdf_extraction.structure_recognizer import NullStructureRecognizer
from pdf_extraction.validator import NullChemicalValidator


class PdfInterfaceTest(unittest.TestCase):
    def test_null_interfaces_are_lightweight(self) -> None:
        self.assertEqual(NullImageExtractor().extract(Path("missing.pdf"), Path("out")), [])
        self.assertEqual(NullStructureRecognizer().recognize([]), [])
        self.assertEqual(NullIdentifierEnricher().enrich_records([]), [])

    def test_null_validator_preserves_record_provenance(self) -> None:
        source = SourceProvenance(
            source_file="paper.pdf",
            page=1,
            extraction_method="test",
            confidence=1.0,
        )
        record = RawChemicalRecord(
            record_id="r1",
            record_type="table_property",
            raw_value="12",
            source=source,
            confidence=0.5,
        )

        results = NullChemicalValidator().validate_records([record])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].target_id, "r1")
        self.assertEqual(results[0].status, "not_checked")
        self.assertEqual(results[0].source, source)


if __name__ == "__main__":
    unittest.main()
