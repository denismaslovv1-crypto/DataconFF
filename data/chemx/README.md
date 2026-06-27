# ChemX local benchmark data

This directory stores local benchmark data for the DataCon/ChemX extraction task.

Current MVP domain:

```text
benzimidazoles/
```

Expected structure:

data/chemx/
  README.md
  benzimidazoles/
    README.md              # dataset README/schema from Hugging Face
    ground_truth.csv       # benchmark table from Hugging Face
    pdfs/                  # source PDF articles used as extractor input
    predictions/           # model/system outputs
    metrics/               # baseline metrics and our evaluation results

File roles:

ground_truth.csv is the benchmark reference table.
README.md inside the domain folder describes the dataset schema.
metrics/ contains official baseline metrics and our computed metrics.
pdfs/ contains source PDFs used for extraction.
predictions/ contains our generated CSV/JSON outputs.

PDF policy:

PDF files are not guaranteed to be shipped directly with the dataset.
They should be downloaded from direct PDF URLs when available.
If only DOI/title is available, unresolved sources should be logged to:

data/chemx/benzimidazoles/missing_pdfs.csv

Manual PDF download is allowed for a small test subset, but the preferred workflow is automated download with logging of failures.

Do not commit large PDFs unless the team explicitly decides to version them.
EOF