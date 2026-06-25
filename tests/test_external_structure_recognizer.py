import unittest

from pdf_extraction.command_tools import CommandToolConfig
from pdf_extraction.external_structure_recognizer import ExternalStructureRecognizer, ExternalStructureRecognizerConfig
from pdf_extraction.models import ExtractedImageAsset, SourceProvenance


class ExternalStructureRecognizerTest(unittest.TestCase):
    def test_parse_molscribe_json_stdout(self) -> None:
        recognizer = ExternalStructureRecognizer(
            ExternalStructureRecognizerConfig(
                molecule_tools=[CommandToolConfig(name="molscribe", command=["unused"])]
            )
        )
        image = ExtractedImageAsset(
            image_id="img1",
            path="img1.png",
            source=SourceProvenance(
                source_file="paper.pdf",
                page=2,
                figure_id="fig1",
                extraction_method="test",
                confidence=1.0,
            ),
        )

        structures = recognizer._parse_output(
            CommandToolConfig(name="molscribe", command=["unused"], output_format="json_stdout"),
            image,
            '{"smiles":"CCO","canonical_SMILES":"CCO","isomeric_SMILES":"CCO","molfile":"mol","confidence":0.91}',
            reaction=False,
        )

        self.assertEqual(len(structures), 1)
        self.assertEqual(structures[0].smiles_raw, "CCO")
        self.assertEqual(structures[0].canonical_SMILES, "CCO")
        self.assertEqual(structures[0].isomeric_SMILES, "CCO")
        self.assertEqual(structures[0].molfile, "mol")
        self.assertEqual(structures[0].source.page, 2)

    def test_parse_osra_smiles_lines(self) -> None:
        recognizer = ExternalStructureRecognizer(ExternalStructureRecognizerConfig())
        image = ExtractedImageAsset(
            image_id="img1",
            path="img1.png",
            source=SourceProvenance(
                source_file="paper.pdf",
                page=1,
                extraction_method="test",
                confidence=1.0,
            ),
        )

        structures = recognizer._parse_output(
            CommandToolConfig(name="osra", command=["unused"], output_format="smiles_lines"),
            image,
            "CCO\nc1ccccc1\n",
            reaction=False,
        )

        self.assertEqual([item.smiles_raw for item in structures], ["CCO", "c1ccccc1"])


if __name__ == "__main__":
    unittest.main()
