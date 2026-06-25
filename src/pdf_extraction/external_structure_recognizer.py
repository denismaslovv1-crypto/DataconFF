from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from pdf_extraction.command_tools import CommandToolConfig, maybe_parse_json, render_command, run_command
from pdf_extraction.models import BoundingBox, ExtractedImageAsset, RecognizedStructure, SourceProvenance
from pdf_extraction.structure_recognizer import StructureRecognitionConfig


class ExternalStructureRecognizerConfig(BaseModel):
    molecule_tools: list[CommandToolConfig] = Field(default_factory=list)
    reaction_tools: list[CommandToolConfig] = Field(default_factory=list)
    min_confidence: float = 0.0


class ExternalStructureRecognizer:
    def __init__(self, config: ExternalStructureRecognizerConfig) -> None:
        self.config = config

    def recognize(
        self,
        images: list[ExtractedImageAsset],
        config: StructureRecognitionConfig | None = None,
    ) -> list[RecognizedStructure]:
        return self._run_tools(images, self.config.molecule_tools, reaction=False)

    def recognize_reactions(
        self,
        images: list[ExtractedImageAsset],
        config: StructureRecognitionConfig | None = None,
    ) -> list[RecognizedStructure]:
        return self._run_tools(images, self.config.reaction_tools, reaction=True)

    def _run_tools(
        self,
        images: list[ExtractedImageAsset],
        tools: list[CommandToolConfig],
        reaction: bool,
    ) -> list[RecognizedStructure]:
        structures: list[RecognizedStructure] = []
        for tool in tools:
            if not tool.enabled:
                continue
            for image in images:
                command = render_command(tool.command, {"image_path": image.path, "image_id": image.image_id})
                completed = run_command(command, tool.timeout_seconds)
                structures.extend(self._parse_output(tool, image, completed.stdout, reaction=reaction))
        return structures

    def _parse_output(
        self,
        tool: CommandToolConfig,
        image: ExtractedImageAsset,
        stdout: str,
        reaction: bool,
    ) -> list[RecognizedStructure]:
        if tool.output_format == "smiles_lines":
            return self._parse_smiles_lines(tool.name, image, stdout)

        payload = maybe_parse_json(stdout)
        if payload is None:
            return []

        if reaction:
            return self._parse_reaction_json(tool.name, image, payload)
        return self._parse_molecule_json(tool.name, image, payload)

    def _parse_smiles_lines(
        self,
        tool_name: str,
        image: ExtractedImageAsset,
        stdout: str,
    ) -> list[RecognizedStructure]:
        structures: list[RecognizedStructure] = []
        for index, line in enumerate(stdout.splitlines(), start=1):
            smiles = line.strip()
            if not smiles:
                continue
            structures.append(self._structure(tool_name, image, index, smiles_raw=smiles, confidence=0.5, raw_output=line))
        return structures

    def _parse_molecule_json(
        self,
        tool_name: str,
        image: ExtractedImageAsset,
        payload: Any,
    ) -> list[RecognizedStructure]:
        rows = payload if isinstance(payload, list) else [payload]
        structures: list[RecognizedStructure] = []
        for index, item in enumerate(rows, start=1):
            if not isinstance(item, dict):
                continue
            confidence = float(item.get("confidence", 0.5))
            if confidence < self.config.min_confidence:
                continue
            structures.append(
                self._structure(
                    tool_name,
                    image,
                    index,
                    smiles_raw=item.get("smiles") or item.get("SMILES"),
                    canonical_SMILES=item.get("canonical_SMILES") or item.get("canonical_smiles"),
                    isomeric_SMILES=item.get("isomeric_SMILES") or item.get("isomeric_smiles"),
                    molfile=item.get("molfile") or item.get("mol"),
                    compound_label=item.get("compound_label") or item.get("label") or image.compound_label,
                    bbox=_bbox_from_value(item.get("bbox")) or image.bbox,
                    confidence=confidence,
                    raw_output=str(item),
                )
            )
        return structures

    def _parse_reaction_json(
        self,
        tool_name: str,
        image: ExtractedImageAsset,
        payload: Any,
    ) -> list[RecognizedStructure]:
        reactions = payload if isinstance(payload, list) else payload.get("reactions", []) if isinstance(payload, dict) else []
        structures: list[RecognizedStructure] = []
        for reaction_index, reaction_payload in enumerate(reactions, start=1):
            reaction_smiles = None
            if isinstance(reaction_payload, dict):
                reaction_smiles = reaction_payload.get("reaction_smiles") or reaction_payload.get("rxn_smiles")
            structures.append(
                self._structure(
                    tool_name,
                    image,
                    reaction_index,
                    reaction_smiles=reaction_smiles,
                    confidence=0.5,
                    raw_output=str(reaction_payload),
                )
            )
        return structures

    def _structure(
        self,
        tool_name: str,
        image: ExtractedImageAsset,
        index: int,
        smiles_raw: str | None = None,
        canonical_SMILES: str | None = None,
        isomeric_SMILES: str | None = None,
        molfile: str | None = None,
        reaction_smiles: str | None = None,
        bbox: BoundingBox | None = None,
        compound_label: str | None = None,
        confidence: float = 0.5,
        raw_output: str | None = None,
    ) -> RecognizedStructure:
        return RecognizedStructure(
            structure_id=f"{image.image_id}_{tool_name}_{index}",
            image_id=image.image_id,
            compound_label=compound_label or image.compound_label,
            bbox=bbox or image.bbox,
            smiles_raw=smiles_raw,
            canonical_SMILES=canonical_SMILES,
            isomeric_SMILES=isomeric_SMILES,
            molfile=molfile,
            reaction_smiles=reaction_smiles,
            raw_output=raw_output,
            recognizer=tool_name,
            source=SourceProvenance(
                source_file=image.source.source_file,
                page=image.source.page,
                figure_id=image.image_id,
                extraction_method=f"external_{tool_name}",
                confidence=confidence,
            ),
            confidence=confidence,
        )


def _bbox_from_value(value: Any) -> BoundingBox | None:
    if isinstance(value, dict):
        return BoundingBox(**value)
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return BoundingBox(x0=value[0], y0=value[1], x1=value[2], y1=value[3])
    return None
