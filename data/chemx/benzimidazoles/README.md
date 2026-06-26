---
dataset_info:
  features:
  - name: smiles
    dtype: string
  - name: doi
    dtype: string
  - name: title
    dtype: string
  - name: publisher
    dtype: string
  - name: year
    dtype: int64
  - name: access
    dtype: int64
  - name: compound_id
    dtype: string
  - name: target_type
    dtype: string
  - name: target_relation
    dtype: string
  - name: target_value
    dtype: string
  - name: target_units
    dtype: string
  - name: bacteria
    dtype: string
  - name: bacteria_unified
    dtype: string
  - name: page_bacteria
    dtype: int64
  - name: origin_bacteria
    dtype: string
  - name: section_bacteria
    dtype: string
  - name: subsection_bacteria
    dtype: string
  - name: page_target
    dtype: int64
  - name: origin_target
    dtype: string
  - name: section_target
    dtype: string
  - name: subsection_target
    dtype: string
  - name: page_scaffold
    dtype: int64
  - name: origin_scaffold
    dtype: string
  - name: page_residue
    dtype: float64
  - name: origin_residue
    dtype: string
  - name: pdf
    dtype: string
  splits:
  - name: train
    num_bytes: 796323
    num_examples: 1721
  download_size: 62035
  dataset_size: 796323
configs:
- config_name: default
  data_files:
  - split: train
    path: data/train-*
license: mit
---

Information about the dataset is detailed in the documentation:  
https://ai-chem.github.io/ChemX/overview/datasets_description.html  
You can find the Croissant file in our GitHub repository:  
https://github.com/ai-chem/ChemX/tree/main/datasets/croissants  