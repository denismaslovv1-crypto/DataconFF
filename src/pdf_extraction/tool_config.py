from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from pdf_extraction.command_tools import CommandToolConfig
from pdf_extraction.external_structure_recognizer import ExternalStructureRecognizer, ExternalStructureRecognizerConfig
from pdf_extraction.image_extractor import ImageExtractionConfig, NullImageExtractor
from pdf_extraction.identifier_enricher import NullIdentifierEnricher
from pdf_extraction.pipeline import PdfPipelineComponents
from pdf_extraction.pymupdf_image_extractor import PyMuPDFImageExtractor
from pdf_extraction.structure_detector import (
    ExternalCommandStructureDetector,
    NullStructureDetector,
    StructureDetectionConfig,
)
from pdf_extraction.validator import NullChemicalValidator


class ImageStageConfig(BaseModel):
    backend: str = "null"
    options: ImageExtractionConfig = Field(default_factory=ImageExtractionConfig)


class ToolPipelineConfig(BaseModel):
    image_extraction: ImageStageConfig = Field(default_factory=ImageStageConfig)
    structure_detection: StructureDetectionConfig = Field(default_factory=StructureDetectionConfig)
    structure_recognition: ExternalStructureRecognizerConfig = Field(default_factory=ExternalStructureRecognizerConfig)


def load_tool_pipeline_config(path: Path) -> ToolPipelineConfig:
    return ToolPipelineConfig.model_validate(json.loads(path.read_text(encoding="utf-8")))


def components_from_tool_config(config: ToolPipelineConfig) -> tuple[PdfPipelineComponents, ImageExtractionConfig]:
    if config.image_extraction.backend == "pymupdf":
        image_extractor = PyMuPDFImageExtractor()
    elif config.image_extraction.backend == "null":
        image_extractor = NullImageExtractor()
    else:
        raise ValueError(f"Unsupported image_extraction backend: {config.image_extraction.backend}")

    if config.structure_detection.tool and config.structure_detection.tool.enabled:
        structure_detector = ExternalCommandStructureDetector(config.structure_detection)
    else:
        structure_detector = NullStructureDetector()

    if config.structure_recognition.molecule_tools or config.structure_recognition.reaction_tools:
        structure_recognizer = ExternalStructureRecognizer(config.structure_recognition)
    else:
        from pdf_extraction.structure_recognizer import NullStructureRecognizer

        structure_recognizer = NullStructureRecognizer()

    return (
        PdfPipelineComponents(
            image_extractor=image_extractor,
            structure_detector=structure_detector,
            structure_recognizer=structure_recognizer,
            identifier_enricher=NullIdentifierEnricher(),
            validator=NullChemicalValidator(),
        ),
        config.image_extraction.options,
    )
