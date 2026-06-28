from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from datacon_workflow.domains.benzimidazoles import CHEMX_COLUMNS
from datacon_workflow.evaluation.chemx_eval import evaluate_predictions
from datacon_workflow.review_records import merge_review_records
from pdf_extraction.models import stable_pdf_stem


ARTICLE_SUMMARY_COLUMNS = (
    "pdf",
    "output_dir",
    "pred_rows",
    "gt_rows",
    "macro_f1",
    "confidence",
    "llm_used",
    "status",
    "error",
    "top_failed_fields",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the full Benzimidazoles batch over all PDFs.")
    parser.add_argument("--pdf-dir", type=Path, required=True)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--llm-mode",
        choices=["never", "auto"],
        default="never",
        help=(
            "LLM fallback mode. 'never' is the final public rules-only mode; "
            "'auto' is an experimental fallback and was not used for final reported metrics."
        ),
    )
    parser.add_argument("--evidence-batch-size", type=int, default=5)
    parser.add_argument("--max-evidence-chunks", type=int, default=80)
    parser.add_argument("--max-concurrent-batches", type=int, default=1)
    parser.add_argument("--resume-existing-batches", action="store_true")
    parser.add_argument("--include", action="append", help="PDF filename to include. Repeat for multiple PDFs.")
    parser.add_argument("--limit", type=int, help="Optional smoke-test cap. Omit for a full run.")
    parser.add_argument("--fail-fast", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    _ensure_repo_python(repo_root)

    available_pdfs = _find_pdfs(args.pdf_dir)
    pdfs = _filter_included_pdfs(available_pdfs, args.include)
    if args.limit is not None:
        pdfs = pdfs[: args.limit]
    if not available_pdfs:
        raise SystemExit(f"No PDF files found in {args.pdf_dir}")
    if not pdfs:
        raise SystemExit("No PDFs selected after applying --include/--limit")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    article_rows: list[dict[str, str]] = []
    manifest_articles: list[dict[str, Any]] = []
    completed = 0
    failed = 0

    for index, pdf in enumerate(pdfs, start=1):
        article_dir = args.output_dir / stable_pdf_stem(pdf)
        article_dir.mkdir(parents=True, exist_ok=True)
        print(f"[{index}/{len(pdfs)}] {pdf.name}")
        result = _run_article(pdf, article_dir, args, repo_root)
        article_rows.append(result["summary_row"])
        manifest_articles.append(result["manifest"])
        if result["summary_row"]["status"] == "ok":
            completed += 1
        else:
            failed += 1
            if args.fail_fast:
                break

    prediction_rows = _collect_prediction_rows(args.output_dir)
    merged_predictions = args.output_dir / "predictions.csv"
    _write_predictions_csv(merged_predictions, prediction_rows)
    review_rows = merge_review_records(args.output_dir)

    full_metrics = None
    evaluation_error = None
    try:
        full_metrics = evaluate_predictions(merged_predictions, args.ground_truth, args.output_dir)
    except Exception as exc:  # Keep manifest/summary available even when eval is misconfigured.
        evaluation_error = str(exc)

    _write_article_summary(article_rows, args.output_dir / "article_summary.csv")
    manifest = {
        "run_started_at_utc": datetime.now(timezone.utc).isoformat(),
        "pdf_dir": str(args.pdf_dir),
        "ground_truth": str(args.ground_truth),
        "output_dir": str(args.output_dir),
        "llm_mode": args.llm_mode,
        "evidence_batch_size": args.evidence_batch_size,
        "max_evidence_chunks": args.max_evidence_chunks,
        "max_concurrent_batches": args.max_concurrent_batches,
        "resume_existing_batches": args.resume_existing_batches,
        "include": args.include,
        "limit": args.limit,
        "pdfs_found": len(available_pdfs),
        "pdfs_selected": len(pdfs),
        "selected_pdfs": [path.name for path in pdfs],
        "completed": completed,
        "failed": failed,
        "merged_prediction_rows": len(prediction_rows),
        "merged_review_rows": len(review_rows),
        "metrics": full_metrics,
        "evaluation_error": evaluation_error,
        "articles": manifest_articles,
    }
    (args.output_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"PDFs found: {len(available_pdfs)}; selected: {len(pdfs)}; completed: {completed}; failed: {failed}")
    print(f"Merged predictions: {merged_predictions}")
    if full_metrics:
        print(f"Full Macro-F1: {full_metrics['macro_f1']:.4f}")
    elif evaluation_error:
        print(f"Evaluation failed: {evaluation_error}")
    return 1 if failed or evaluation_error else 0


def _ensure_repo_python(repo_root: Path) -> None:
    expected = repo_root / ".venv" / "Scripts" / "python.exe"
    if not expected.exists():
        raise SystemExit(
            "\n".join(
                [
                    "Repository interpreter is missing.",
                    f"current working directory: {Path.cwd()}",
                    f"checked interpreter path: {expected}",
                    f"command that could not run: {expected} scripts\\run_benzimidazoles_full.py",
                    "what to create/install: create the repository .venv with .\\setup_project_env.cmd",
                ]
            )
        )
    if Path(sys.executable).resolve() != expected.resolve():
        raise SystemExit(
            "\n".join(
                [
                    "This script must be run with the repository-local interpreter.",
                    f"current working directory: {Path.cwd()}",
                    f"checked interpreter path: {expected}",
                    f"current interpreter: {sys.executable}",
                    f"command that could not run: {expected} scripts\\run_benzimidazoles_full.py",
                    "what to create/install: rerun with .\\.venv\\Scripts\\python.exe",
                ]
            )
        )


def _find_pdfs(pdf_dir: Path) -> list[Path]:
    return sorted(
        (path for path in pdf_dir.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"),
        key=lambda path: path.name.lower(),
    )


def _filter_included_pdfs(pdfs: list[Path], includes: list[str] | None) -> list[Path]:
    if not includes:
        return pdfs
    requested = {include.lower() for include in includes}
    selected = [pdf for pdf in pdfs if pdf.name.lower() in requested]
    missing = sorted(requested - {pdf.name.lower() for pdf in selected})
    if missing:
        available = ", ".join(pdf.name for pdf in pdfs)
        raise SystemExit(
            f"Included PDF filename(s) not found: {', '.join(missing)}\n"
            f"Available PDFs: {available}"
        )
    return selected


def _run_article(pdf: Path, article_dir: Path, args: argparse.Namespace, repo_root: Path) -> dict[str, Any]:
    command = _build_article_command(pdf, article_dir, args)
    status = "ok"
    error = ""
    try:
        completed = subprocess.run(
            command,
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        (article_dir / "runner_stdout.txt").write_text(completed.stdout, encoding="utf-8")
        (article_dir / "runner_stderr.txt").write_text(completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            status = "failed"
            error = _first_non_empty(completed.stderr, completed.stdout, f"exit code {completed.returncode}")
    except Exception as exc:
        status = "failed"
        error = str(exc)

    summary = _load_article_outputs(pdf, article_dir, status, error, args.ground_truth)
    manifest = {
        "pdf": str(pdf),
        "output_dir": str(article_dir),
        "status": summary["status"],
        "error": summary["error"],
        "pred_rows": int(summary["pred_rows"] or 0),
        "gt_rows": int(summary["gt_rows"] or 0),
        "macro_f1": _maybe_float(summary["macro_f1"]),
        "confidence": summary["confidence"],
        "llm_used": summary["llm_used"],
        "command": _display_command(command),
    }
    return {"summary_row": summary, "manifest": manifest}


def _build_article_command(pdf: Path, article_dir: Path, args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        str(Path("scripts") / "run_hybrid_benzimidazoles.py"),
        "--pdf",
        str(pdf),
        "--ground-truth",
        str(args.ground_truth),
        "--output-dir",
        str(article_dir),
        "--llm-mode",
        args.llm_mode,
        "--evidence-batch-size",
        str(args.evidence_batch_size),
        "--max-evidence-chunks",
        str(args.max_evidence_chunks),
        "--max-concurrent-batches",
        str(args.max_concurrent_batches),
    ]
    if args.resume_existing_batches:
        command.append("--resume-existing-batches")
    return command


def _load_article_outputs(
    pdf: Path,
    article_dir: Path,
    status: str,
    error: str,
    ground_truth_csv: Path | None = None,
) -> dict[str, str]:
    predictions_csv = article_dir / "predictions.csv"
    metrics_json = article_dir / "metrics.json"
    confidence_json = article_dir / "confidence_report.json"
    summary_json = article_dir / "hybrid_summary.json"
    field_metrics_csv = article_dir / "field_metrics.csv"

    pred_rows = _count_csv_rows(predictions_csv)
    metrics = _read_json(metrics_json)
    confidence = _read_json(confidence_json)
    hybrid_summary = _read_json(summary_json)

    if status == "ok" and not predictions_csv.exists():
        status = "failed"
        error = error or "missing predictions.csv"
    if ground_truth_csv and predictions_csv.exists():
        try:
            metrics = evaluate_predictions(
                predictions_csv,
                ground_truth_csv,
                article_dir,
                benchmark_pdf_name=stable_pdf_stem(pdf),
            )
        except Exception as exc:
            status = "failed"
            error = error or f"evaluation failed: {exc}"

    return {
        "pdf": str(pdf),
        "output_dir": str(article_dir),
        "pred_rows": str(pred_rows),
        "gt_rows": str(metrics.get("ground_truth_count", "")) if metrics else "",
        "macro_f1": _format_float(metrics.get("macro_f1")) if metrics else "",
        "confidence": str(confidence.get("confidence", "")) if confidence else "",
        "llm_used": str(bool(hybrid_summary.get("llm_ran", False))).lower() if hybrid_summary else "",
        "status": status,
        "error": error,
        "top_failed_fields": _top_failed_fields(field_metrics_csv),
    }


def _collect_prediction_rows(output_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for predictions_csv in sorted(output_dir.glob("*/predictions.csv"), key=lambda path: str(path).lower()):
        with predictions_csv.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != CHEMX_COLUMNS:
                raise ValueError(f"{predictions_csv} must use exactly {','.join(CHEMX_COLUMNS)}")
            rows.extend({column: row.get(column, "") for column in CHEMX_COLUMNS} for row in reader)
    return rows


def _write_predictions_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CHEMX_COLUMNS, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _write_article_summary(rows: list[dict[str, str]], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ARTICLE_SUMMARY_COLUMNS, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8", newline="") as handle:
        return sum(1 for _row in csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _top_failed_fields(path: Path, limit: int = 3) -> str:
    if not path.exists():
        return ""
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    scored = [
        (row.get("field", ""), float(row.get("f1", "0") or 0))
        for row in rows
        if row.get("field") and float(row.get("f1", "0") or 0) < 1.0
    ]
    scored.sort(key=lambda item: (item[1], item[0]))
    return ";".join(field for field, _score in scored[:limit])


def _first_non_empty(*values: str) -> str:
    for value in values:
        cleaned = value.strip()
        if cleaned:
            lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
            return lines[-1] if lines else cleaned
    return ""


def _format_float(value: object) -> str:
    return f"{float(value):.6f}" if value is not None else ""


def _maybe_float(value: str) -> float | None:
    return float(value) if value else None


def _display_command(command: list[str]) -> list[str]:
    displayed = list(command)
    if displayed:
        displayed[0] = r".\.venv\Scripts\python.exe"
    return displayed


if __name__ == "__main__":
    raise SystemExit(main())
