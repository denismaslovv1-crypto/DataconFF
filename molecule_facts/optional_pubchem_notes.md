# Optional PubChem Notes

## Purpose

PubChem can be used as optional identifier enrichment, not as a replacement for source extraction.

Use it only when the article provides a reliable molecule name, InChI, InChIKey, CAS, or other identifier that can be saved together with the API query and response.

## When to use PubChem

Use PubChem for:

- name -> CID lookup;
- InChIKey -> CID lookup;
- CID -> canonical/isomeric SMILES;
- CID -> InChI / InChIKey;
- CID -> molecular formula / molecular weight;
- checking synonyms for a known compound.

## When not to use PubChem

Do not use PubChem to invent missing molecules.

Avoid enrichment when:

- the article only shows a generic scaffold;
- compound labels require unresolved R-group substitution;
- the name is an ambiguous abbreviation;
- the compound is a novel unpublished derivative not present in PubChem;
- several PubChem hits are plausible and no source-backed disambiguation exists.

## Provenance requirement

Every enrichment result must store:

```text
source_record_id
input_identifier
input_identifier_type
pubchem_query_url_or_payload
pubchem_cid
returned_canonical_smiles
returned_isomeric_smiles
returned_inchi
returned_inchikey
retrieval_timestamp
confidence
validation_status
```

Do not overwrite the raw source value. Store enriched identifiers as a separate normalized/enriched layer.

## Suggested workflow

```text
raw article value
  -> normalize identifier string
  -> query PubChem
  -> save raw API response or selected fields
  -> validate with RDKit if available
  -> link enrichment record back to source evidence
```

## Benzimidazoles policy

For the first benchmark-positive Benzimidazoles workflow, PubChem is optional and low priority.

Use PubChem only if:

- high-priority fields already work;
- the molecule has a clear source-backed name or identifier;
- the enrichment improves `smiles` without creating false positives.

If unsure, keep:

```text
smiles = NOT_DETECTED
```

## Relation to existing code examples

The existing NIST/PubChem parser prototype is useful as a pattern for API enrichment, but it should be refactored before production use:

- remove hardcoded relative paths;
- add provenance;
- split fetching/parsing/normalization;
- cache raw API responses;
- validate outputs;
- add tests.
