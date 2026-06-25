from __future__ import annotations

import argparse
from pathlib import Path

from pdf_extraction.page_rendering import parse_pages, render_pdf_pages, write_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render PDF pages to PNG files with a JSON manifest.")
    parser.add_argument("--pdf", required=True, help="Input PDF path.")
    parser.add_argument("--output-dir", required=True, help="Directory for rendered page PNG files.")
    parser.add_argument("--pages", help="Optional 1-based pages, for example: 1,3,5-7.")
    parser.add_argument("--zoom", type=float, default=2.0, help="Render zoom. 2.0 gives 144 DPI-equivalent output.")
    parser.add_argument("--manifest", help="Manifest path. Defaults to <output-dir>/page_renders.json.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = Path(args.output_dir)
    manifest_path = Path(args.manifest) if args.manifest else output_dir / "page_renders.json"
    rendered = render_pdf_pages(
        pdf_path=Path(args.pdf),
        output_dir=output_dir,
        pages=parse_pages(args.pages),
        zoom=args.zoom,
    )
    write_manifest(rendered, manifest_path)
    print(f"Rendered pages: {len(rendered)}")
    print(f"Output directory: {output_dir}")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
