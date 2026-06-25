import unittest

from pdf_extraction.pipeline import PdfPipelineComponents
from pdf_extraction.identifier_enricher import NullIdentifierEnricher
from pdf_extraction.image_extractor import NullImageExtractor
from pdf_extraction.structure_detector import NullStructureDetector
from pdf_extraction.structure_recognizer import NullStructureRecognizer
from pdf_extraction.validator import NullChemicalValidator


class FakeChemistryExtractor:
    def extract(self, source_file, tables, text_blocks):
        return []


class FakeTableExtractor:
    def extract(self, pdf_path):
        return []


class FakeTextExtractor:
    def extract(self, pdf_path):
        return 0, {}, []


class PdfPipelineComponentsTest(unittest.TestCase):
    def test_default_optional_components_are_noop(self) -> None:
        components = PdfPipelineComponents(
            text_extractor=FakeTextExtractor(),
            table_extractor=FakeTableExtractor(),
            chemistry_extractor=FakeChemistryExtractor(),
            image_extractor=NullImageExtractor(),
            structure_detector=NullStructureDetector(),
            structure_recognizer=NullStructureRecognizer(),
            identifier_enricher=NullIdentifierEnricher(),
            validator=NullChemicalValidator(),
        )

        self.assertEqual(components.image_extractor.extract.__self__.__class__.__name__, "NullImageExtractor")
        self.assertEqual(components.structure_recognizer.recognize([]), [])
        self.assertEqual(components.identifier_enricher.enrich_records([]), [])
        self.assertEqual(components.validator.validate_records([]), [])


if __name__ == "__main__":
    unittest.main()
