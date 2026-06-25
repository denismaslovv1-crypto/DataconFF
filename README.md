# Datacon Extraction

RAG-assisted workspace for chemical data extraction, dataset preparation, and future molecule selection workflows.

The current priority is:

1. Build a local RAG memory layer over project Markdown notes and reusable examples.
2. Build a universal PDF extraction MVP.
3. Preserve raw extraction results with source provenance.
4. Add chemical record extraction, normalization, and validation.

## Project Layout

```text
project_docs/         Architecture, roadmap, decisions, parser plans.
methodology_notes/    Notes about chemical data, RAG, PDF extraction, validation.
molecule_facts/       Factual molecule and dataset records.
code_examples/        Reusable extraction examples and drafts.
src/rag_core/         Local RAG indexing and retrieval layer.
src/pdf_extraction/   PDF parser MVP and optional structure-recognition interfaces.
rag_index/            Generated local RAG/Chroma indexes.
tests/                Unit tests for core project utilities.
```

Logical groups:

```text
core/            src/rag_core, src/pdf_extraction, config, tests, project docs.
examples/        code_examples and reusable parser drafts.
artifacts/       data and rag_index working outputs.
external_tools/  local optional environments and wrappers for MolScribe, DECIMER, OSRA, RxnScribe, YOLO.
```

## Python environments

This project uses separate local Python environments. They are not stored in Git; recreate them locally.

Main project:

```powershell
.\setup_project_env.cmd
.\.venv\Scripts\python.exe -m pytest
```

MolScribe:

```powershell
.\setup_molscribe_env.cmd
.\.venv-molscribe\Scripts\python.exe scripts\run_molscribe_one.py --image path\to\image.png --allow-download
```

Optional external structure tools:

```powershell
.\setup_external_envs.cmd
```

This creates/updates MolScribe and DECIMER environments. DECIMER is intentionally separate because it is a heavy detector stack.

Do not use plain python, py, system Python, or Codex runtime.
Always call the interpreter explicitly.

## Local RAG

Create and activate a project virtual environment before running commands:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Build the index:

```powershell
python -m rag_core build --root . --index-dir rag_index
```

Query the notes:

```powershell
python -m rag_core query "PDF table extraction provenance" --index-dir rag_index --top-k 5
```

The retriever returns only relevant chunks with collection, source file, heading, line range, and score.

## Vector RAG For Methodology Notes

The vector layer is prepared for OpenAI-compatible embedding APIs and ChromaDB.
Here "OpenAI-compatible" means the project uses the OpenAI Python SDK against a provider that exposes the same `/embeddings` API shape. The embeddings do not have to come from OpenAI; in the default config they come from OpenRouter.

Install vector dependencies:

```powershell
scripts/install_vector_deps.ps1
```

Copy `.env.example` to `.env`, then fill:

```env
OPENMODEL_API_KEY=your_openmodel_key
OPENROUTER_API_KEY=your_openrouter_key
```

The default model config is in [config/rag_models.json](config/rag_models.json):

- text requests: `deepseek-v4-flash` through `https://api.openmodel.ai/v1`
- embeddings: `nvidia/llama-nemotron-embed-vl-1b-v2:free` through `https://openrouter.ai/api/v1`

Build a Chroma vector DB from `methodology_notes`:

```powershell
scripts/vector.ps1 build
```

Query the vector DB:

```powershell
scripts/vector.ps1 query "PDF table extraction with source provenance"
```

Generated vector files are stored in `rag_index/vector_chroma/`.
Use `-Collection molecule_facts` later when factual molecule records become large enough to justify semantic search. This uses the same `rag_core`; it is not a separate RAG system.

## PDF Extraction

Parse all PDFs from `data/pdf_raw` into raw JSON and CSV:

```powershell
python -m pdf_extraction
```

Outputs are written to:

```text
data/pdf_parsed/
  chemical_records.csv
  *.raw.json
```

The parser keeps provenance for extracted values:

```text
source_file -> page -> section/table/figure -> extraction_method -> confidence
```

Optional image/structure stages are configured through JSON:

```powershell
python -m pdf_extraction --tool-config config/pdf_tools.example.json
```

The example config is safe by default: YOLO, MolScribe, OSRA, and RxnScribe tools are present but disabled. Enable them only after installing the corresponding local tools/checkpoints.

Optional local dependencies:

```powershell
pip install -e .[pdf-images]
pip install -e .[yolo]
```

External tools:

- MolScribe: molecule image -> SMILES/MOL.
- OSRA: molecule image/PDF -> SMILES.
- RxnScribe: reaction diagram -> reactants, conditions, products. The repository is not vendored here; only the optional command interface is kept.
- YOLO/DocLayout-YOLO: figure/molecule crop detection before recognition.

### Manual PyMuPDF molecule crop workflow

Before adding YOLO, use a manual crop loop to verify that MolScribe works on molecule fragments from real PDFs:

```powershell
.\.venv\Scripts\python.exe scripts\render_pdf_pages.py `
  --pdf "data\pdf_raw\article.pdf" `
  --pages 1-3 `
  --zoom 2 `
  --output-dir "data\pdf_pages\article"
```

Open a rendered page PNG, choose a molecule bounding box in pixel coordinates, then crop that PDF region:

```powershell
.\.venv\Scripts\python.exe scripts\crop_pdf_region.py `
  --pdf "data\pdf_raw\article.pdf" `
  --page 2 `
  --bbox "120,300,420,620" `
  --bbox-units pixels `
  --zoom 2 `
  --output "data\molecule_crops\article_p002_mol001.png"
```

The crop command writes a sidecar JSON with source file, page, bbox, method, and confidence. Use the same `--zoom` value that was used for page rendering when the bbox is measured from the PNG.

Run MolScribe on the crop:

```powershell
.\.venv-molscribe\Scripts\python.exe scripts\run_molscribe_one.py `
  --image "data\molecule_crops\article_p002_mol001.png" `
  --allow-download `
  --output "data\molecule_crops\article_p002_mol001.molscribe.json"
```

After the normal PDF pipeline has produced `data/pdf_parsed/<article>.raw.json`, import the crop recognition result into the parsed JSON and CSV outputs:

```powershell
.\.venv\Scripts\python.exe scripts\import_molscribe_crop.py `
  --output-dir "data\pdf_parsed" `
  --sidecar "data\molecule_crops\article_p002_mol001.png.json" `
  --molscribe-json "data\molecule_crops\article_p002_mol001.molscribe.json" `
  --figure-id "Figure 1" `
  --compound-label "1" `
  --caption "Figure 1. Biological profiles of lead compound 1." `
  --min-confidence 0.5
```

### Automatic DECIMER segmentation workflow

DECIMER Segmentation is kept in a separate environment because it is a heavy ML detector:

```powershell
.\setup_decimer_env.cmd
```

Then run the automatic parser:

```powershell
.\parse_pdf_auto.cmd "data\pdf_raw\article.pdf" 1-3
```

This runs:

```text
base PDF pipeline -> page rendering -> DECIMER structure crops -> MolScribe -> import into raw JSON/CSV
```

Outputs are written under:

```text
data/pdf_pages/
data/molecule_crops_auto/
data/pdf_parsed/
```
