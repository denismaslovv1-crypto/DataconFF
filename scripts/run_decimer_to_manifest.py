from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run DECIMER Segmentation on one rendered page image.")
    parser.add_argument("--image", required=True, help="Rendered PDF page image.")
    parser.add_argument("--output-dir", required=True, help="Directory for segmented molecule crops.")
    parser.add_argument("--manifest", required=True, help="Output detection manifest JSON.")
    parser.add_argument("--source-file", required=True, help="Original PDF file name/path for provenance.")
    parser.add_argument("--page", required=True, type=int, help="1-based source PDF page number.")
    parser.add_argument("--confidence", type=float, default=1.0, help="Default confidence for DECIMER crops.")
    parser.add_argument("--expand", action="store_true", default=True, help="Use DECIMER mask expansion.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

    import cv2
    from decimer_segmentation import segment_chemical_structures

    image_path = Path(args.image)
    output_dir = Path(args.output_dir)
    manifest_path = Path(args.manifest)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    image = cv2.imread(str(image_path))
    if image is None:
        raise SystemExit(f"Could not read image: {image_path}")

    segments = segment_chemical_structures(image, expand=args.expand)
    detections = []
    source_file = Path(args.source_file).name

    for index, segment in enumerate(segments, start=1):
        crop_id = f"{image_path.stem}_decimer_{index:03d}"
        crop_path = output_dir / f"{crop_id}.png"
        sidecar_path = crop_path.with_suffix(crop_path.suffix + ".json")
        cv2.imwrite(str(crop_path), segment)
        height, width = segment.shape[:2]
        sidecar = {
            "source_file": source_file,
            "page": args.page,
            "crop_id": crop_id,
            "image_path": str(crop_path),
            "image_width": width,
            "image_height": height,
            "extraction_method": "decimer_segmentation",
            "confidence": args.confidence,
        }
        sidecar_path.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8")
        detections.append(
            {
                "image_id": crop_id,
                "image_path": str(crop_path),
                "sidecar_path": str(sidecar_path),
                "source_file": source_file,
                "page": args.page,
                "class_name": "chemical_structure",
                "confidence": args.confidence,
                "width": width,
                "height": height,
            }
        )

    manifest_path.write_text(json.dumps({"detections": detections}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "detections": len(detections)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
