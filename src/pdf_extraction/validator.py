from __future__ import annotations

from typing import Protocol

from pdf_extraction.models import IdentifierEnrichment, RawChemicalRecord, RecognizedStructure, ValidationResult


class ChemicalValidator(Protocol):
    """Validate raw records and identifiers without deleting uncertain data."""

    def validate_records(self, records: list[RawChemicalRecord]) -> list[ValidationResult]:
        """Validate extracted property rows, units, ranges, and provenance."""

    def validate_structures(self, structures: list[RecognizedStructure]) -> list[ValidationResult]:
        """Validate SMILES/MOL candidates, normally through RDKit later."""

    def validate_identifiers(self, enrichments: list[IdentifierEnrichment]) -> list[ValidationResult]:
        """Validate CID, SMILES, InChI, InChIKey, CAS, and PDB identifiers."""


class NullChemicalValidator:
    """Marks items as not checked while preserving pipeline contracts."""

    def validate_records(self, records: list[RawChemicalRecord]) -> list[ValidationResult]:
        return [
            ValidationResult(
                target_id=record.record_id,
                target_type="raw_record",
                status="not_checked",
                validator="null",
                source=record.source,
            )
            for record in records
        ]

    def validate_structures(self, structures: list[RecognizedStructure]) -> list[ValidationResult]:
        return [
            ValidationResult(
                target_id=structure.structure_id,
                target_type="structure",
                status="not_checked",
                validator="null",
                source=structure.source,
            )
            for structure in structures
        ]

    def validate_identifiers(self, enrichments: list[IdentifierEnrichment]) -> list[ValidationResult]:
        return [
            ValidationResult(
                target_id=enrichment.enrichment_id,
                target_type="identifier_enrichment",
                status="not_checked",
                validator="null",
                source=enrichment.source,
            )
            for enrichment in enrichments
        ]
