from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pdf_extraction.exporters import write_compound_labels_csv, write_document_json, write_records_csv
from pdf_extraction.identifier_enricher import IdentifierEnricher, NullIdentifierEnricher
from pdf_extraction.image_extractor import ImageExtractionConfig, ImageExtractor, NullImageExtractor
from pdf_extraction.models import ParsedPdfDocument, RawChemicalRecord, stable_pdf_stem
from pdf_extraction.structure_detector import NullStructureDetector, StructureDetector
from pdf_extraction.structure_mapper import apply_structure_mappings, structures_to_records
from pdf_extraction.structure_recognizer import NullStructureRecognizer, StructureRecognizer
from pdf_extraction.validator import ChemicalValidator, NullChemicalValidator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "pdf_raw"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "pdf_parsed"


def _default_text_extractor() -> Any:
    from pdf_extraction.text_extractor import PdfTextExtractor

    return PdfTextExtractor()


def _default_table_extractor() -> Any:
    from pdf_extraction.table_extractor import PdfTableExtractor

    return PdfTableExtractor()


def _default_chemistry_extractor() -> Any:
    from pdf_extraction.chemistry_extractor import ChemistryRecordExtractor

    return ChemistryRecordExtractor()


@dataclass
class PdfPipelineComponents:
    text_extractor: Any = field(default_factory=_default_text_extractor)
    table_extractor: Any = field(default_factory=_default_table_extractor)
    chemistry_extractor: Any = field(default_factory=_default_chemistry_extractor)
    image_extractor: ImageExtractor = field(default_factory=NullImageExtractor)
    structure_detector: StructureDetector = field(default_factory=NullStructureDetector)
    structure_recognizer: StructureRecognizer = field(default_factory=NullStructureRecognizer)
    identifier_enricher: IdentifierEnricher = field(default_factory=NullIdentifierEnricher)
    validator: ChemicalValidator = field(default_factory=NullChemicalValidator)


class PdfExtractionPipeline:
    def __init__(self, components: PdfPipelineComponents | None = None) -> None:
        self.components = components or PdfPipelineComponents()

    def parse_pdf(
        self,
        pdf_path: Path,
        output_dir: Path | None = None,
        run_optional_stages: bool = False,
        image_config: ImageExtractionConfig | None = None,
    ) -> ParsedPdfDocument:
        page_count, metadata, text_blocks = self.components.text_extractor.extract(pdf_path)
        tables = self.components.table_extractor.extract(pdf_path)
        chemical_records = self.components.chemistry_extractor.extract(pdf_path.name, tables, text_blocks)

        images = []
        recognized_structures = []
        identifier_enrichments = []
        validation_results = []

        if run_optional_stages:
            asset_output_dir = self._asset_output_dir(pdf_path, output_dir)
            images = self.components.image_extractor.extract(pdf_path, asset_output_dir, image_config)
            structure_images = self.components.structure_detector.detect(images, asset_output_dir)
            if structure_images is not images:
                images.extend([image for image in structure_images if image.image_id not in {existing.image_id for existing in images}])
            recognized_structures = self.components.structure_recognizer.recognize(structure_images)
            recognized_structures.extend(self.components.structure_recognizer.recognize_reactions(structure_images))
            identifier_enrichments = self.components.identifier_enricher.enrich_structures(recognized_structures)
            chemical_records = apply_structure_mappings(chemical_records, recognized_structures)
            chemical_records.extend(structures_to_records(pdf_path.name, recognized_structures))
            validation_results = self.components.validator.validate_records(chemical_records)
            validation_results.extend(self.components.validator.validate_structures(recognized_structures))
            validation_results.extend(self.components.validator.validate_identifiers(identifier_enrichments))

        return ParsedPdfDocument(
            source_file=pdf_path.name,
            page_count=page_count,
            metadata=metadata,
            text_blocks=text_blocks,
            tables=tables,
            images=images,
            recognized_structures=recognized_structures,
            identifier_enrichments=identifier_enrichments,
            validation_results=validation_results,
            chemical_records=chemical_records,
        )

    def parse_input(
        self,
        input_path: Path,
        output_dir: Path,
        run_optional_stages: bool = False,
        image_config: ImageExtractionConfig | None = None,
    ) -> list[RawChemicalRecord]:
        pdf_paths = _collect_pdf_paths(input_path)
        if not pdf_paths:
            raise FileNotFoundError(f"No PDF files found in {input_path}")

        all_records: list[RawChemicalRecord] = []
        output_dir.mkdir(parents=True, exist_ok=True)

        for pdf_path in pdf_paths:
            document = self.parse_pdf(
                pdf_path,
                output_dir=output_dir,
                run_optional_stages=run_optional_stages,
                image_config=image_config,
            )
            json_path = output_dir / f"{stable_pdf_stem(pdf_path)}.raw.json"
            write_document_json(document, json_path)
            all_records.extend(document.chemical_records)

        write_records_csv(all_records, output_dir / "chemical_records.csv")
        write_compound_labels_csv(all_records, output_dir / "compound_labels.csv")
        return all_records

    def _asset_output_dir(self, pdf_path: Path, output_dir: Path | None) -> Path:
        base_dir = output_dir or pdf_path.parent
        return base_dir / "assets" / stable_pdf_stem(pdf_path)


def parse_pdf(
    pdf_path: Path,
    output_dir: Path | None = None,
    run_optional_stages: bool = False,
    image_config: ImageExtractionConfig | None = None,
    components: PdfPipelineComponents | None = None,
) -> ParsedPdfDocument:
    return PdfExtractionPipeline(components).parse_pdf(
        pdf_path,
        output_dir=output_dir,
        run_optional_stages=run_optional_stages,
        image_config=image_config,
    )


def parse_input(
    input_path: Path,
    output_dir: Path,
    run_optional_stages: bool = False,
    image_config: ImageExtractionConfig | None = None,
    components: PdfPipelineComponents | None = None,
) -> list[RawChemicalRecord]:
    return PdfExtractionPipeline(components).parse_input(
        input_path,
        output_dir,
        run_optional_stages=run_optional_stages,
        image_config=image_config,
    )


def _collect_pdf_paths(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted(input_path.glob("*.pdf"))


def resolve_project_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse scientific PDFs into raw chemical records.")
    parser.add_argument(
        "input",
        nargs="?",
        default=str(DEFAULT_INPUT_DIR),
        help="PDF file or directory with PDF files. Relative paths are resolved from the project root.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for raw JSON and CSV outputs. Relative paths are resolved from the project root.",
    )
    parser.add_argument(
        "--run-optional-stages",
        action="store_true",
        help="Run configured image, structure, enrichment, and validation hooks. Defaults are no-op adapters.",
    )
    parser.add_argument(
        "--tool-config",
        help="JSON config for image extraction, YOLO detection, MolScribe/OSRA/RxnScribe commands.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    components = None
    image_config = None
    run_optional_stages = args.run_optional_stages
    if args.tool_config:
        from pdf_extraction.tool_config import components_from_tool_config, load_tool_pipeline_config

        components, image_config = components_from_tool_config(
            load_tool_pipeline_config(resolve_project_path(args.tool_config))
        )
        run_optional_stages = True
    records = parse_input(
        resolve_project_path(args.input),
        resolve_project_path(args.output_dir),
        run_optional_stages=run_optional_stages,
        image_config=image_config,
        components=components,
    )
    print(f"Parsed chemical record candidates: {len(records)}")
    print(f"Output directory: {Path(args.output_dir).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
