from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run MolScribe on one molecule image and print JSON.")
    parser.add_argument("--image", required=True, help="Input molecule image.")
    parser.add_argument("--model-path", default=os.environ.get("MOLSCRIBE_MODEL_PATH"), help="MolScribe checkpoint path.")
    parser.add_argument("--device", default=os.environ.get("MOLSCRIBE_DEVICE", "cpu"), help="Torch device.")
    parser.add_argument("--allow-download", action="store_true", help="Download checkpoint from Hugging Face if model path is absent.")
    parser.add_argument("--output", help="Optional JSON output path.")
    return parser


def canonicalize_smiles(smiles: str | None) -> dict[str, Any]:
    if not smiles:
        return {"canonical_SMILES": None, "isomeric_SMILES": None, "smiles_valid": False}
    try:
        from rdkit import Chem
    except ImportError:
        return {"canonical_SMILES": None, "isomeric_SMILES": None, "smiles_valid": None}

    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        return {"canonical_SMILES": None, "isomeric_SMILES": None, "smiles_valid": False}
    return {
        "canonical_SMILES": Chem.MolToSmiles(molecule, canonical=True, isomericSmiles=False),
        "isomeric_SMILES": Chem.MolToSmiles(molecule, canonical=True, isomericSmiles=True),
        "smiles_valid": True,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    import torch
    from molscribe import MolScribe

    model_path = args.model_path
    if not model_path and args.allow_download:
        from huggingface_hub import hf_hub_download

        model_path = hf_hub_download("yujieq/MolScribe", "swin_base_char_aux_1m.pth")
    if not model_path:
        raise SystemExit("Missing MolScribe checkpoint. Pass --model-path, set MOLSCRIBE_MODEL_PATH, or use --allow-download.")

    model = MolScribe(model_path, device=torch.device(args.device))
    output = model.predict_image_file(args.image, return_atoms_bonds=True, return_confidence=True)
    smiles = output.get("smiles")
    payload = {
        "smiles": smiles,
        **canonicalize_smiles(smiles),
        "molfile": output.get("molfile"),
        "confidence": output.get("confidence", 0.5),
        "atoms": output.get("atoms"),
        "bonds": output.get("bonds"),
    }
    text = json.dumps(payload, ensure_ascii=False)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
