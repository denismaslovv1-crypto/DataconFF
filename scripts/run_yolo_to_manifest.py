from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run YOLO on one image and write crop manifest JSON.")
    parser.add_argument("--image", required=True, help="Input image path.")
    parser.add_argument("--output-dir", required=True, help="Directory for detected crops.")
    parser.add_argument("--manifest", required=True, help="Output manifest JSON path.")
    parser.add_argument("--model", default=os.environ.get("YOLO_MODEL_PATH"), help="YOLO model path. Defaults to YOLO_MODEL_PATH.")
    parser.add_argument("--conf", type=float, default=0.25, help="YOLO confidence threshold.")
    parser.add_argument("--include-classes", nargs="*", default=None, help="Optional class names to keep.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.model:
        raise SystemExit("Missing YOLO model path. Pass --model or set YOLO_MODEL_PATH.")

    from PIL import Image
    from ultralytics import YOLO

    image_path = Path(args.image)
    output_dir = Path(args.output_dir)
    manifest_path = Path(args.manifest)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    image = Image.open(image_path).convert("RGB")
    model = YOLO(args.model)
    results = model(str(image_path), conf=args.conf)

    detections = []
    for result_index, result in enumerate(results, start=1):
        names = result.names or {}
        boxes = result.boxes
        if boxes is None:
            continue
        for box_index, box in enumerate(boxes, start=1):
            class_id = int(box.cls[0].item()) if box.cls is not None else -1
            class_name = str(names.get(class_id, class_id))
            if args.include_classes and class_name not in args.include_classes:
                continue
            confidence = float(box.conf[0].item()) if box.conf is not None else 0.0
            x0, y0, x1, y1 = [float(value) for value in box.xyxy[0].tolist()]
            crop = image.crop((x0, y0, x1, y1))
            crop_name = f"{image_path.stem}_yolo{result_index}_{box_index}_{class_name}.png"
            crop_path = output_dir / crop_name
            crop.save(crop_path)
            detections.append(
                {
                    "image_id": crop_path.stem,
                    "image_path": str(crop_path),
                    "bbox": {"x0": x0, "y0": y0, "x1": x1, "y1": y1},
                    "class_name": class_name,
                    "confidence": confidence,
                    "width": crop.width,
                    "height": crop.height,
                }
            )

    manifest_path.write_text(json.dumps({"detections": detections}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "detections": len(detections)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
