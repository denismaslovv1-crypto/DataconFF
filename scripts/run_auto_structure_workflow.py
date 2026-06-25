from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from pdf_extraction.crop_structure_importer import import_molscribe_crop
from pdf_extraction.page_rendering import parse_pages, render_pdf_pages
from pdf_extraction.models import stable_pdf_stem
from pdf_extraction.structure_quality import generic_structure_reason


@dataclass(frozen=True)
class ImportedStructureSummary:
    source_file: str
    page: int
    compound_label: str
    confidence: float
    smiles: str
    crop_image_path: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Auto-detect molecule crops with DECIMER, recognize with MolScribe, and import.")
    parser.add_argument("--pdf", required=True, help="Input PDF path.")
    parser.add_argument("--output-dir", default="data/pdf_parsed", help="PDF pipeline output directory.")
    parser.add_argument("--pages", help="Optional 1-based pages, for example: 1,3,5-7.")
    parser.add_argument("--zoom", type=float, default=2.0, help="Page render zoom.")
    parser.add_argument("--page-dir", help="Rendered page output dir.")
    parser.add_argument("--crop-dir", default="data/molecule_crops_auto", help="Auto crop output dir.")
    parser.add_argument("--decimer-python", default=".venv-decimer/Scripts/python.exe", help="Python executable with DECIMER.")
    parser.add_argument("--molscribe-python", default=".venv-molscribe/Scripts/python.exe", help="Python executable with MolScribe.")
    parser.add_argument("--min-confidence", type=float, default=0.5, help="Minimum MolScribe confidence to import.")
    parser.add_argument("--compound-label-prefix", default="auto", help="Prefix for generated compound labels.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pdf_path = Path(args.pdf)
    output_dir = Path(args.output_dir)
    stem = stable_pdf_stem(pdf_path)
    page_dir = Path(args.page_dir) if args.page_dir else Path("data/pdf_pages") / stem
    crop_dir = Path(args.crop_dir) / stem
    decimer_python = Path(args.decimer_python)
    molscribe_python = Path(args.molscribe_python)

    if not decimer_python.exists():
        raise SystemExit(f"DECIMER Python not found: {decimer_python}")
    if not molscribe_python.exists():
        raise SystemExit(f"MolScribe Python not found: {molscribe_python}")

    rendered_pages = render_pdf_pages(pdf_path, page_dir, pages=parse_pages(args.pages), zoom=args.zoom)
    total_detections = 0
    total_imported = 0
    imported: list[ImportedStructureSummary] = []

    print(f"Rendered pages: {len(rendered_pages)}")

    for page in rendered_pages:
        page_crop_dir = crop_dir / f"p{page.page:03d}"
        manifest_path = page_crop_dir / "decimer_detections.json"
        print(f"\nPage {page.page}: running DECIMER segmentation...")
        _run_quiet(
            [
                str(decimer_python),
                "scripts/run_decimer_to_manifest.py",
                "--image",
                page.image_path,
                "--output-dir",
                str(page_crop_dir),
                "--manifest",
                str(manifest_path),
                "--source-file",
                str(pdf_path),
                "--page",
                str(page.page),
            ]
        )
        manifest = _read_json(manifest_path)
        detections = manifest.get("detections", [])
        total_detections += len(detections)
        print(f"Page {page.page}: DECIMER detections = {len(detections)}")

        for index, detection in enumerate(detections, start=1):
            image_path = Path(detection["image_path"])
            molscribe_json = image_path.with_suffix(".molscribe.json")
            compound_label = f"{args.compound_label_prefix}_p{page.page}_{index:03d}"
            _run_quiet(
                [
                    str(molscribe_python),
                    "scripts/run_molscribe_one.py",
                    "--image",
                    str(image_path),
                    "--allow-download",
                    "--output",
                    str(molscribe_json),
                ]
            )
            molscribe = _read_json(molscribe_json)
            smiles = molscribe.get("canonical_SMILES") or molscribe.get("smiles") or ""
            confidence = float(molscribe.get("confidence", 0.0))
            generic_reason = generic_structure_reason(smiles, molscribe.get("molfile"))
            try:
                import_molscribe_crop(
                    output_dir=output_dir,
                    sidecar_path=Path(detection["sidecar_path"]),
                    molscribe_json_path=molscribe_json,
                    figure_id=f"Page {page.page}",
                    compound_label=compound_label,
                    min_confidence=args.min_confidence,
                )
            except ValueError as exc:
                print(f"  skipped {compound_label}: confidence={confidence:.3f}, reason={exc}")
                continue
            total_imported += 1
            imported.append(
                ImportedStructureSummary(
                    source_file=pdf_path.name,
                    page=page.page,
                    compound_label=compound_label,
                    confidence=confidence,
                    smiles=smiles,
                    crop_image_path=str(image_path),
                )
            )
            marker = f", generic={generic_reason}" if generic_reason else ""
            print(f"  imported {compound_label}: confidence={confidence:.3f}{marker}, SMILES={smiles}, crop={image_path}")

    print("\nRecognition summary")
    print("-------------------")
    if imported:
        for item in imported:
            print(
                f"{item.source_file} | page={item.page} | label={item.compound_label} | "
                f"confidence={item.confidence:.3f} | SMILES={item.smiles}"
            )
    else:
        print("No structures were imported.")
    print("\nTotals")
    print(f"  rendered_pages: {len(rendered_pages)}")
    print(f"  decimer_detections: {total_detections}")
    print(f"  imported_structures: {total_imported}")
    print(f"  csv_output_dir: {output_dir}")
    return 0


def _run_quiet(command: list[str]) -> None:
    completed = subprocess.run(command, check=False, text=True, capture_output=True)
    if completed.returncode != 0:
        if completed.stdout:
            print(completed.stdout)
        if completed.stderr:
            print(completed.stderr)
        raise SystemExit(completed.returncode)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
