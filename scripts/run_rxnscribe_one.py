from __future__ import annotations

import argparse
import json
import os


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run RxnScribe on one reaction diagram image and print JSON.")
    parser.add_argument("--image", required=True, help="Input reaction diagram image.")
    parser.add_argument("--model-path", default=os.environ.get("RXNSCRIBE_MODEL_PATH"), help="RxnScribe checkpoint path.")
    parser.add_argument("--device", default=os.environ.get("RXNSCRIBE_DEVICE", "cpu"), help="Torch device.")
    parser.add_argument("--allow-download", action="store_true", help="Download checkpoint from Hugging Face if model path is absent.")
    parser.add_argument("--no-molscribe", action="store_true", help="Disable RxnScribe internal MolScribe call.")
    parser.add_argument("--no-ocr", action="store_true", help="Disable RxnScribe OCR.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    import torch
    from rxnscribe import RxnScribe

    model_path = args.model_path
    if not model_path and args.allow_download:
        from huggingface_hub import hf_hub_download

        model_path = hf_hub_download("yujieq/RxnScribe", "pix2seq_reaction_full.ckpt")
    if not model_path:
        raise SystemExit("Missing RxnScribe checkpoint. Pass --model-path, set RXNSCRIBE_MODEL_PATH, or use --allow-download.")

    model = RxnScribe(model_path, device=torch.device(args.device))
    predictions = model.predict_image_file(args.image, molscribe=not args.no_molscribe, ocr=not args.no_ocr)
    print(json.dumps({"reactions": predictions}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
