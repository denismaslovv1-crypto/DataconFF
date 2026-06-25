from __future__ import annotations

import argparse
from pathlib import Path

from pdf_extraction.crop_structure_importer import import_molscribe_crop


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import one manual PDF crop MolScribe result into parsed PDF JSON and CSV outputs."
    )
    parser.add_argument("--output-dir", default="data/pdf_parsed", help="PDF pipeline output directory.")
    parser.add_argument("--sidecar", required=True, help="Crop sidecar JSON from scripts/crop_pdf_region.py.")
    parser.add_argument("--molscribe-json", required=True, help="MolScribe JSON output from scripts/run_molscribe_one.py.")
    parser.add_argument("--figure-id", help="Figure label, for example: Figure 1.")
    parser.add_argument("--caption", help="Optional figure caption text.")
    parser.add_argument("--compound-label", help="Optional compound label, for example: 1 or 4d.")
    parser.add_argument("--min-confidence", type=float, default=0.0, help="Reject MolScribe results below this confidence.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    document = import_molscribe_crop(
        output_dir=Path(args.output_dir),
        sidecar_path=Path(args.sidecar),
        molscribe_json_path=Path(args.molscribe_json),
        figure_id=args.figure_id,
        caption=args.caption,
        compound_label=args.compound_label,
        min_confidence=args.min_confidence,
    )
    print(f"Updated parsed document: {document.source_file}")
    print(f"Recognized structures: {len(document.recognized_structures)}")
    print(f"Chemical records: {len(document.chemical_records)}")
    print(f"CSV rebuilt under: {Path(args.output_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
