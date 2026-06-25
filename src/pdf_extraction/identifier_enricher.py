from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

from pdf_extraction.models import IdentifierEnrichment, RawChemicalRecord, RecognizedStructure


class IdentifierEnrichmentConfig(BaseModel):
    use_pubchem: bool = True
    use_opsin: bool = False
    use_rcsb_pdb: bool = False
    enrich_text_records: bool = False
    timeout_seconds: float = 20.0


class IdentifierEnricher(Protocol):
    """Resolve raw names/SMILES/IDs into stable chemical identifiers."""

    def enrich_records(
        self,
        records: list[RawChemicalRecord],
        config: IdentifierEnrichmentConfig | None = None,
    ) -> list[IdentifierEnrichment]:
        """Optional name-based enrichment. Disabled by the main PDF pipeline by default."""

    def enrich_structures(
        self,
        structures: list[RecognizedStructure],
        config: IdentifierEnrichmentConfig | None = None,
    ) -> list[IdentifierEnrichment]:
        """Enrich recognized image structures with CID, SMILES, InChI, InChIKey, CAS, or PDB ID."""


class NullIdentifierEnricher:
    """No-op implementation for offline or raw-only extraction runs."""

    def enrich_records(
        self,
        records: list[RawChemicalRecord],
        config: IdentifierEnrichmentConfig | None = None,
    ) -> list[IdentifierEnrichment]:
        return []

    def enrich_structures(
        self,
        structures: list[RecognizedStructure],
        config: IdentifierEnrichmentConfig | None = None,
    ) -> list[IdentifierEnrichment]:
        return []
