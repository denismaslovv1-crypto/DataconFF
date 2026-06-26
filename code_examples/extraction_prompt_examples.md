# Extraction Prompt Examples

## Purpose

Reusable prompt templates for evidence-bounded ChemX extraction. These prompts are not a substitute for validation. They must be used only on parsed evidence chunks, not on a whole PDF corpus.

## General rules for all prompts

- Return JSON only.
- Return one JSON array.
- Do not include Markdown.
- Do not explain.
- Do not deduplicate unless the domain config says so.
- If evidence is missing, write `NOT_DETECTED`.
- Do not invent numbers, units, SMILES, molecule names, or provenance.
- Preserve values exactly when normalization is handled downstream.

## Benzimidazoles extraction prompt

### System

```text
You are a domain-specific chemical information extraction assistant.
You specialize in small-molecule antibiotics and SAR/MIC tables.
You extract only source-backed records from the provided evidence chunk.
You never invent values that are not present in the evidence.
```

### User

```text
Extract Benzimidazoles ChemX records from the evidence chunk below.

Return a JSON array only. No Markdown, no commentary, no extra text.

Fields for each object:
- compound_id: string. Article-local molecule identifier, e.g. "5a", "11h", "Compound 3".
- smiles: string. Full source-backed SMILES. If absent, use "NOT_DETECTED".
- target_type: string. Either "MIC" or "pMIC".
- target_relation: string. One of "=", "<", ">". If no relation is shown, use "=".
- target_value: number or string range. Numeric MIC/pMIC value without units. Preserve a range if the evidence gives a range.
- target_units: string. MIC/pMIC units exactly as shown, e.g. "µg/mL", "mg/L", "mmol/L".
- bacteria: string. Bacterium name exactly as shown or a clear source-backed abbreviation, e.g. "S. aureus", "E. coli".

Extraction rules:
1. Extract each MIC or pMIC measurement as a separate object.
2. If one compound has values for multiple bacteria, return separate objects.
3. Extract only values supported by the evidence chunk.
4. Do not infer SMILES from a scaffold or R-group table.
5. If only a generic scaffold is present, set smiles to "NOT_DETECTED".
6. If a required field is missing, use "NOT_DETECTED".

Evidence metadata:
source_file: {source_file}
page: {page}
chunk_id: {chunk_id}

Evidence chunk:
{evidence_text}
```

## JSON repair prompt

Use only after a model returned invalid JSON.

```text
You returned invalid JSON.
Repair the output into a valid JSON array only.
Do not add new records.
Do not add new values.
Do not explain.

Invalid output:
{invalid_output}
```

## Evidence verification prompt

Use this when a record is produced by LLM extraction and must be checked against its evidence.

```text
Check whether the proposed record is fully supported by the evidence.
Return JSON only:
{
  "supported": true_or_false,
  "unsupported_fields": ["field_name"],
  "reason": "short reason"
}

Record:
{record_json}

Evidence:
{evidence_text}
```

## Complexes fallback prompt

```text
Extract organometallic complex or chelate ligand records from the evidence chunk.
Return JSON array only with fields:
compound_id, compound_name, SMILES, SMILES_type, target

Rules:
- Extract each lgK/logK target value as a separate record.
- Use NOT_DETECTED for missing fields.
- Do not invent SMILES.
- Extract only source-backed records.
```

## Co-crystals fallback prompt

```text
Extract co-crystal photostability records from the evidence chunk.
Return JSON array only with fields:
name_cocrystal, ratio_cocrystal, name_drug, SMILES_drug, name_coformer, SMILES_coformer, photostability_change

Rules:
- photostability_change must be one of: decrease, does not change, increase.
- Use NOT_DETECTED for missing fields.
- Do not invent SMILES.
- Extract only source-backed records.
```
