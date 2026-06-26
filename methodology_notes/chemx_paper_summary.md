# ChemX Paper Summary

## Why this paper matters for the project

ChemX is a benchmark for automated information extraction from chemistry papers. It is directly aligned with this repository because the target is not a general PDF chatbot, but structured extraction from scientific literature into domain-specific dataset rows.

## Benchmark structure

ChemX contains ten datasets across two tracks:

- small molecules;
- nanomaterials.

Each dataset has its own schema. A prediction must match the selected domain schema, not a universal chemical record schema.

## Core task

Given a scientific article, extract all target chemical records for one ChemX domain and save them in the expected tabular format.

Fields can include:

- molecule or material identifiers;
- SMILES or material formula;
- biological/physical target values;
- units;
- experimental context;
- text/table/figure-derived values.

## Evaluation

ChemX reports field-level Precision, Recall, F1, and Macro-F1.

For the hackathon, the practical goal is to beat the published single-agent baseline on at least one domain. The first target domain is `Benzimidazoles` because the baseline is low and the high-value fields are mostly extractable from tables/text.

## Important findings from the paper

### 1. Chemical extraction is multimodal

Important values may appear in:

- text;
- tables;
- figures;
- molecular depictions;
- plots;
- supplementary materials.

A plain text-only pipeline is often insufficient.

### 2. Single-agent extraction is brittle

The ChemX single-agent pipeline converts PDF content into Markdown, describes images, and then asks an LLM to produce structured output. This is useful as a baseline, but it is hard to control and tends to fail on numerical values, SMILES, complex tables, and ambiguous context.

### 3. Nanomaterials are harder than small molecules

Nanomaterial datasets contain more fields, more hierarchical relationships, more missing values, and more inconsistent terminology. Small molecule domains are a better first target for a two-day implementation.

### 4. SMILES extraction remains difficult

The paper reports weak SMILES extraction quality for several small molecule datasets. For this project, SMILES must not be hallucinated. It should be extracted only when source-backed or enriched through a saved external API response.

### 5. Evaluation must be column-aware

Aggregate Macro-F1 can hide field-level failures. The project should always save field-level metrics and use them for iteration.

## Design implications for this repository

Use a controlled workflow:

```text
PDF
  -> deterministic parsing
  -> evidence chunks
  -> domain extractor
  -> normalization
  -> validation
  -> ChemX-compatible CSV
  -> field-level metrics
```

Use RAG as project memory and evidence retrieval support, not as the main extraction engine.

Use LLMs only on bounded evidence chunks and validate every output with a schema.

## Recommended file placement

Keep this summary in:

```text
methodology_notes/chemx_paper_summary.md
```

Keep the original ChemX PDF as a raw source/reference file if repository size allows it. The Markdown summary is better for RAG indexing; the PDF is better as a source of figures, tables, and exact appendix prompts.
