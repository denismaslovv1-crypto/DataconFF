import unittest

from pdf_extraction.chemistry_extractor import ChemistryRecordExtractor


class ChemistryRecordExtractorTest(unittest.TestCase):
    def test_parse_compound_line_with_parenthesized_name(self) -> None:
        extractor = ChemistryRecordExtractor()

        parsed = extractor._parse_compound_line(
            "4d(MCL-603) 0.061\u00b10.006 22 0.048\u00b10.003 1.3:458:1 5.2"
        )

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.compound_label, "4d")
        self.assertEqual(parsed.molecule_name, "MCL-603")
        self.assertEqual(parsed.values, ["0.061\u00b10.006", "22", "0.048\u00b10.003", "1.3:458:1", "5.2"])

    def test_infer_opioid_binding_property_names(self) -> None:
        extractor = ChemistryRecordExtractor()

        names = extractor._infer_property_names("Compound Ki SEM DAMGO Naltindole U69 Selectivity CLogP")

        self.assertEqual(names[:5], ["mu_Ki", "delta_Ki", "kappa_Ki", "selectivity", "CLogP"])


if __name__ == "__main__":
    unittest.main()
