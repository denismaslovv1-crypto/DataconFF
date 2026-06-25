from __future__ import annotations

import argparse
from pathlib import Path

from pdf_extraction.page_rendering import crop_pdf_region, parse_bbox, write_sidecar


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crop one PDF page region to a molecule image PNG.")
    parser.add_argument("--pdf", required=True, help="Input PDF path.")
    parser.add_argument("--page", required=True, type=int, help="1-based PDF page number.")
    parser.add_argument("--bbox", required=True, help="Crop box as x0,y0,x1,y1.")
    parser.add_argument(
        "--bbox-units",
        choices=("pixels", "points"),
        default="pixels",
        help="Coordinate units. Use pixels when bbox was read from a rendered PNG at the same zoom.",
    )
    parser.add_argument("--zoom", type=float, default=2.0, help="Render zoom used for pixel coordinates and output crop.")
    parser.add_argument("--output", required=True, help="Output crop PNG path.")
    parser.add_argument("--crop-id", help="Optional stable crop identifier.")
    parser.add_argument("--sidecar", help="Sidecar JSON path. Defaults to <output>.json.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_path = Path(args.output)
    crop = crop_pdf_region(
        pdf_path=Path(args.pdf),
        output_path=output_path,
        page_number=args.page,
        bbox=parse_bbox(args.bbox),
        bbox_units=args.bbox_units,
        zoom=args.zoom,
        crop_id=args.crop_id,
    )
    sidecar_path = Path(args.sidecar) if args.sidecar else output_path.with_suffix(output_path.suffix + ".json")
    write_sidecar(crop, sidecar_path)
    print(f"Crop image: {output_path}")
    print(f"Sidecar: {sidecar_path}")
    print(f"Page: {crop.page}")
    print(f"BBox pixels: {crop.bbox_pixels}")
    print(f"BBox points: {crop.bbox_points}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
