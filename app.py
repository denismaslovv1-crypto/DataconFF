"""Streamlit demo for the final ChemX Benzimidazoles workflow."""
from __future__ import annotations

import csv
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from datacon_workflow.domains.benzimidazoles import CHEMX_COLUMNS
from datacon_workflow.orchestration import AgenticOrchestrationConfig
from datacon_workflow.orchestrator import run_benzimidazole_workflow


REPO_ROOT = Path(__file__).resolve().parent
PDF_DIR = REPO_ROOT / "data" / "chemx" / "benzimidazoles" / "pdfs"
GROUND_TRUTH_CSV = REPO_ROOT / "data" / "chemx" / "benzimidazoles" / "ground_truth.csv"
OUTPUTS_DIR = REPO_ROOT / "outputs"
UI_OUTPUT_ROOT = OUTPUTS_DIR / "benzimidazoles" / "ui"
UPLOAD_DIR = UI_OUTPUT_ROOT / "uploads"
DEFAULT_FULL_OUTPUT = OUTPUTS_DIR / "benzimidazoles_full"
# Keep Streamlit defaults and public copy in sync whenever the final metrics
# artifact path changes.
DEFAULT_FULL_OUTPUT_LABEL = "outputs/benzimidazoles_full"
BASELINE_MACRO_F1 = 0.217
LOW_ROW_THRESHOLD = 5
KEY_CHEMX_FIELDS = {
    "target_units",
    "bacteria",
    "target_value",
    "target_type",
    "target_relation",
}
STALE_OUTPUT_MARKERS = (
    "_rules_complete",
    "_rules_final",
    "_debug",
    "_probe",
    "_dedup_fix",
)


def available_pdfs(pdf_dir: Path = PDF_DIR) -> list[Path]:
    if not pdf_dir.exists():
        return []
    return sorted(pdf_dir.glob("*.pdf"), key=lambda path: path.name.lower())


def available_result_dirs(outputs_dir: Path = OUTPUTS_DIR) -> list[Path]:
    if not outputs_dir.exists():
        return []
    return sorted(
        [
            path for path in outputs_dir.iterdir()
            if path.is_dir()
            and (path / "metrics.json").exists()
            and is_public_result_dir(path)
        ],
        key=lambda path: path.name.lower(),
    )


def is_public_result_dir(path: Path) -> bool:
    if path.resolve() == DEFAULT_FULL_OUTPUT.resolve():
        return True
    name = path.name.lower()
    return not any(marker in name for marker in STALE_OUTPUT_MARKERS)


def safe_stem(filename: str) -> str:
    stem = Path(filename).stem.strip() or "uploaded"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", stem)


def output_dir_for(pdf_path: Path, output_root: Path = UI_OUTPUT_ROOT) -> Path:
    return output_root / safe_stem(pdf_path.name)


def resolve_repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def display_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read_json(path: Path | None) -> Any:
    if path is None or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def count_csv_rows(path: Path | None) -> int:
    return len(read_csv_rows(path))


def save_uploaded_pdf(uploaded_file: Any, upload_dir: Path = UPLOAD_DIR) -> Path:
    upload_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = upload_dir / f"{safe_stem(uploaded_file.name)}.pdf"
    pdf_path.write_bytes(uploaded_file.getvalue())
    return pdf_path


def load_full_run(output_dir: Path) -> dict[str, Any]:
    json_artifacts = {
        "predictions.json": output_dir / "predictions.json",
        "predictions_with_evidence.json": output_dir / "predictions_with_evidence.json",
        "run_manifest.json": output_dir / "run_manifest.json",
    }
    return {
        "output_dir": output_dir,
        "metrics": read_json(output_dir / "metrics.json") or {},
        "field_metrics": read_csv_rows(output_dir / "field_metrics.csv"),
        "article_summary": read_csv_rows(output_dir / "article_summary.csv"),
        "predictions": read_csv_rows(output_dir / "predictions.csv"),
        "artifacts": {
            "metrics.json": output_dir / "metrics.json",
            "field_metrics.csv": output_dir / "field_metrics.csv",
            "article_summary.csv": output_dir / "article_summary.csv",
            "predictions.csv": output_dir / "predictions.csv",
            "run_manifest.json": output_dir / "run_manifest.json",
            **json_artifacts,
        },
        "json_artifacts": json_artifacts,
    }


def article_display_rows(article_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in article_rows:
        pred_rows = _int_value(row.get("pred_rows"))
        gt_rows = _int_value(row.get("gt_rows"))
        macro_f1 = _float_value(row.get("macro_f1"))
        flags = article_flags(pred_rows, gt_rows)
        rows.append(
            {
                "pdf": Path(row.get("pdf", "")).name,
                "prediction rows": pred_rows,
                "gt_rows": gt_rows,
                "Macro-F1": "" if macro_f1 is None else f"{macro_f1:.4f}",
                "status": row.get("status", ""),
                "flags": ", ".join(flags),
            }
        )
    return rows


def article_flags(pred_rows: int, gt_rows: int) -> list[str]:
    flags: list[str] = []
    if pred_rows == 0 and gt_rows > 0:
        flags.append("zero rows")
    elif 0 < pred_rows < LOW_ROW_THRESHOLD and gt_rows > 0:
        flags.append("low rows")
    return flags


def public_article_display_rows(display_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in row.items() if key != "flags"} for row in display_rows]


def zero_row_articles(article_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    return [
        {
            "pdf": Path(row.get("pdf", "")).name,
            "prediction rows": _int_value(row.get("pred_rows")),
            "gt_rows": _int_value(row.get("gt_rows")),
            "status": row.get("status", ""),
        }
        for row in article_rows
        if _int_value(row.get("pred_rows")) == 0 and _int_value(row.get("gt_rows")) > 0
    ]


def metric_regression_rows(article_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    regression_keys = ("regression", "delta", "previous_macro_f1", "metric_change")
    return [
        row for row in article_rows
        if any(key in row and str(row.get(key, "")).strip() for key in regression_keys)
    ]


def weak_key_field_rows(article_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in article_rows:
        weak_fields = [
            field.strip()
            for field in str(row.get("top_failed_fields", "")).split(";")
            if field.strip() in KEY_CHEMX_FIELDS
        ]
        if weak_fields:
            rows.append(
                {
                    "pdf": Path(row.get("pdf", "")).name,
                    "Macro-F1": row.get("macro_f1", ""),
                    "weak key fields": ", ".join(weak_fields),
                }
            )
    return rows


def single_prediction_rows(state: Any) -> list[dict[str, str]]:
    return [record.chemx_row() for record in state.normalized_records]


def provenance_rows(state: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, record in enumerate(state.normalized_records, start=1):
        rows.append(
            {
                "#": index,
                "compound_id": record.compound_id,
                "bacteria": record.bacteria,
                "target_value": record.target_value,
                "page": record.evidence.page,
                "method": record.evidence.extraction_method,
                "confidence": f"{record.evidence.confidence:.2f}",
                "row_id": record.evidence.row_id or "",
            }
        )
    return rows


def run_single_article(pdf_path: Path, output_dir: Path) -> Any:
    output_dir.mkdir(parents=True, exist_ok=True)
    ground_truth = GROUND_TRUTH_CSV if GROUND_TRUTH_CSV.exists() else None
    return run_benzimidazole_workflow(
        pdf_path,
        output_dir,
        ground_truth,
        agentic_config=AgenticOrchestrationConfig(mode="disabled"),
    )


def full_run_command(pdf_dir: Path, ground_truth_csv: Path, output_dir: Path) -> list[str]:
    repo_python = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    return [
        str(repo_python),
        str(REPO_ROOT / "scripts" / "run_benzimidazoles_full.py"),
        "--pdf-dir",
        str(pdf_dir),
        "--ground-truth",
        str(ground_truth_csv),
        "--output-dir",
        str(output_dir),
        "--llm-mode",
        "never",
    ]


def display_full_run_command(pdf_dir: Path, ground_truth_csv: Path, output_dir: Path) -> str:
    parts = [
        ".\\.venv\\Scripts\\python.exe",
        "scripts/run_benzimidazoles_full.py",
        "--pdf-dir",
        display_path(pdf_dir),
        "--ground-truth",
        display_path(ground_truth_csv),
        "--output-dir",
        display_path(output_dir),
        "--llm-mode",
        "never",
    ]
    return " ".join(f'"{part}"' if " " in part else part for part in parts)


def run_full_dataset(pdf_dir: Path, ground_truth_csv: Path, output_dir: Path) -> subprocess.CompletedProcess[str]:
    command = full_run_command(pdf_dir, ground_truth_csv, output_dir)
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _int_value(value: object) -> int:
    try:
        return int(float(str(value or "0")))
    except ValueError:
        return 0


def _float_value(value: object) -> float | None:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def main() -> None:
    try:
        import streamlit as st
    except ImportError as exc:
        raise RuntimeError(
            "Streamlit is not installed. Install it manually in .venv to run the UI: "
            ".\\.venv\\Scripts\\python.exe -m pip install streamlit"
        ) from exc

    st.set_page_config(page_title="DataCon ChemX Benzimidazoles", layout="wide")
    st.title("DataCon ChemX Benzimidazoles")
    st.caption("Final rules-only workflow: PDF -> evidence -> rules -> validation -> ChemX CSV -> evaluation")

    if "saved_output_dir" not in st.session_state:
        st.session_state.saved_output_dir = DEFAULT_FULL_OUTPUT_LABEL

    saved_tab, single_tab, full_tab = st.tabs(["Saved Full-Run Results", "Run Single Article", "Run Full Dataset"])

    with saved_tab:
        render_saved_results(st)

    with single_tab:
        render_single_article(st)

    with full_tab:
        render_full_dataset(st)


def render_saved_results(st: Any) -> None:
    result_dirs = available_result_dirs()
    result_options = [display_path(path) for path in result_dirs]
    current = str(st.session_state.get("saved_output_dir", DEFAULT_FULL_OUTPUT))
    default_label = display_path(resolve_repo_path(current))
    options = sorted(set(result_options + [default_label]))
    selected = st.selectbox(
        "Output directory",
        options,
        index=options.index(default_label) if default_label in options else 0,
        key="saved_output_select",
    )
    custom = st.text_input("Custom output directory", value=selected, key="saved_output_custom")
    output_dir = resolve_repo_path(custom)
    st.session_state.saved_output_dir = str(output_dir)

    required = ["metrics.json", "field_metrics.csv", "article_summary.csv", "predictions.csv"]
    missing = [name for name in required if not (output_dir / name).exists()]
    if missing:
        st.warning(f"Missing required report artifact(s): {', '.join(missing)}")
        return

    data = load_full_run(output_dir)
    metrics = data["metrics"]
    article_rows = data["article_summary"]
    predictions = data["predictions"]
    zero_rows = zero_row_articles(article_rows)

    st.subheader("Dataset Summary")
    cols = st.columns(6)
    macro_f1 = float(metrics.get("macro_f1", 0.0) or 0.0)
    cols[0].metric("Macro-F1", f"{macro_f1:.4f}")
    cols[1].metric("Baseline", f"{BASELINE_MACRO_F1:.3f}")
    cols[2].metric("Predictions", int(metrics.get("prediction_count", len(predictions)) or 0))
    cols[3].metric("Ground truth", int(metrics.get("ground_truth_count", 0) or 0))
    cols[4].metric("PDFs", len(article_rows))
    cols[5].metric("Zero-row PDFs", len(zero_rows))
    improvement = macro_f1 - BASELINE_MACRO_F1
    multiplier = macro_f1 / BASELINE_MACRO_F1 if BASELINE_MACRO_F1 else 0.0
    if macro_f1 >= BASELINE_MACRO_F1:
        st.success(
            f"Macro-F1 = {macro_f1:.4f}, which is +{improvement:.4f} above the published "
            f"single-agent baseline ({BASELINE_MACRO_F1:.3f}), or about {multiplier:.2f}x higher."
        )
    else:
        st.error(f"Macro-F1 is below the published single-agent baseline ({BASELINE_MACRO_F1:.3f}).")

    st.subheader("Article Summary")
    display_rows = article_display_rows(article_rows)
    st.dataframe(public_article_display_rows(display_rows), width="stretch", hide_index=True)
    if zero_rows:
        st.warning("Zero-row PDFs with corrected gt_rows")
        st.dataframe(zero_rows, width="stretch", hide_index=True)

    low_rows = [row for row in display_rows if row["flags"] == "low rows"]
    if low_rows:
        with st.expander("Developer details: article flags"):
            st.dataframe(low_rows, width="stretch", hide_index=True)

    regressions = metric_regression_rows(article_rows)
    if regressions:
        st.warning("Metric regression columns detected in article_summary.csv")
        st.dataframe(regressions, width="stretch", hide_index=True)

    st.subheader("Field Metrics")
    st.dataframe(data["field_metrics"], width="stretch", hide_index=True)

    weak_rows = weak_key_field_rows(article_rows)
    if weak_rows:
        with st.expander("Weak key ChemX fields"):
            st.dataframe(weak_rows, width="stretch", hide_index=True)

    with st.expander("Predictions Preview"):
        st.dataframe(predictions[:500], width="stretch", hide_index=True)
        if len(predictions) > 500:
            st.caption(f"Showing first 500 of {len(predictions)} rows.")

    render_json_preview(st, data["json_artifacts"])
    render_downloads(st, data["artifacts"])
    st.caption(f"Loaded artifacts from {display_path(output_dir)}")


def render_single_article(st: Any) -> None:
    pdfs = available_pdfs()
    labels = [path.name for path in pdfs]
    if not labels:
        st.warning(f"No PDFs found under {display_path(PDF_DIR)}.")
        selected_pdf = ""
    else:
        default_index = labels.index("jhet.3467.pdf") if "jhet.3467.pdf" in labels else 0
        selected_pdf = st.selectbox("Bundled PDF", labels, index=default_index)
    uploaded = st.file_uploader("Or upload a PDF", type=["pdf"])
    if uploaded is not None:
        pdf_path = save_uploaded_pdf(uploaded)
    elif selected_pdf:
        pdf_path = next(path for path in pdfs if path.name == selected_pdf)
    else:
        st.info("No PDF selected.")
        return

    default_output = output_dir_for(pdf_path)
    output_text = st.text_input("Output directory", value=display_path(default_output), key="single_output_dir")
    output_dir = resolve_repo_path(output_text)
    st.caption(f"Selected PDF: {display_path(pdf_path)}")
    st.caption("Single article runs are rules-only with agentic sidecars disabled.")

    if not st.button("Run Rules-Only Extraction", type="primary", key="run_single"):
        return

    with st.spinner("Running rules-only extraction and corrected PDF-stem evaluation..."):
        state = run_single_article(pdf_path, output_dir)

    predictions = single_prediction_rows(state)
    metrics = state.metrics or {}
    cols = st.columns(4)
    cols[0].metric("Prediction rows", len(predictions))
    cols[1].metric("Ground truth rows", int(metrics.get("ground_truth_count", 0) or 0))
    cols[2].metric("Raw candidates", len(state.raw_records))
    cols[3].metric("Validation errors", len(state.validation_errors))

    if metrics:
        st.metric("Macro-F1", f"{float(metrics.get('macro_f1', 0.0)):.4f}")

    st.subheader("Predictions")
    if predictions:
        st.dataframe(predictions, width="stretch", hide_index=True)
    else:
        st.warning("No validated prediction rows were produced.")

    if metrics:
        st.subheader("Field Metrics")
        st.dataframe(metrics.get("field_metrics", []), width="stretch", hide_index=True)

    if state.validation_errors:
        st.subheader("Validation Errors")
        st.dataframe(
            [{"#": index, "error": error} for index, error in enumerate(state.validation_errors, start=1)],
            width="stretch",
            hide_index=True,
        )

    if state.normalized_records:
        st.subheader("Evidence / Provenance")
        st.dataframe(provenance_rows(state), width="stretch", hide_index=True)
        labels = [
            f"{index}. {record.compound_id} | {record.bacteria} | {record.target_value} {record.target_units}"
            for index, record in enumerate(state.normalized_records, start=1)
        ]
        selected = st.selectbox("Record evidence", range(len(labels)), format_func=lambda index: labels[index])
        record = state.normalized_records[selected]
        st.json(record.evidence.model_dump(mode="json"))
        st.text_area("Evidence text", record.evidence.evidence_text, height=160)

    artifacts = {
        "predictions.csv": state.prediction_csv,
        "predictions.json": state.prediction_json,
        "metrics.json": output_dir / "metrics.json",
        "field_metrics.csv": output_dir / "field_metrics.csv",
        "evidence.json": output_dir / "evidence.json",
    }
    render_downloads(st, artifacts)
    st.caption(f"Artifacts written to {display_path(output_dir)}")
    st.caption(f"CSV columns: {', '.join(CHEMX_COLUMNS)}")


def render_full_dataset(st: Any) -> None:
    pdf_dir_text = st.text_input("PDF directory", value=display_path(PDF_DIR), key="full_pdf_dir")
    ground_truth_text = st.text_input("Ground truth CSV", value=display_path(GROUND_TRUTH_CSV), key="full_gt")
    output_text = st.text_input(
        "Output directory",
        value=DEFAULT_FULL_OUTPUT_LABEL,
        key="full_output_dir",
    )
    pdf_dir = resolve_repo_path(pdf_dir_text)
    ground_truth = resolve_repo_path(ground_truth_text)
    output_dir = resolve_repo_path(output_text)
    command = full_run_command(pdf_dir, ground_truth, output_dir)
    with st.expander("Developer details"):
        st.code(display_full_run_command(pdf_dir, ground_truth, output_dir), language="powershell")
    confirm = st.checkbox("I understand this will run the full 30-PDF rules-only workflow.", key="confirm_full_run")
    if not st.button("Run Full Dataset", type="primary", disabled=not confirm, key="run_full"):
        last = st.session_state.get("last_full_run")
        if isinstance(last, dict):
            st.info(f"Last command exit code: {last['returncode']}")
            st.code(last.get("stdout", ""), language="text")
            if last.get("stderr"):
                st.code(last["stderr"], language="text")
        return

    with st.spinner("Running full rules-only dataset workflow..."):
        completed = run_full_dataset(pdf_dir, ground_truth, output_dir)

    st.session_state.last_full_run = {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "command": command,
    }
    st.session_state.saved_output_dir = str(output_dir)
    if completed.returncode == 0:
        st.success("Full dataset run completed. Saved Full-Run Results now points at this output directory.")
    else:
        st.error(f"Full dataset run failed with exit code {completed.returncode}.")
    st.code(completed.stdout, language="text")
    if completed.stderr:
        st.code(completed.stderr, language="text")


def render_downloads(st: Any, artifacts: dict[str, Path | None]) -> None:
    st.subheader("Downloads")
    existing = [(name, path) for name, path in artifacts.items() if path is not None and path.exists()]
    if not existing:
        st.info("No downloadable artifacts found yet.")
        return
    columns = st.columns(min(4, len(existing)))
    for index, (name, path) in enumerate(existing):
        mime = "application/json" if path.suffix == ".json" else "text/csv"
        columns[index % len(columns)].download_button(
            f"Download {name}",
            path.read_bytes(),
            file_name=name,
            mime=mime,
            key=f"download_{name}_{path}",
        )


def render_json_preview(st: Any, artifacts: dict[str, Path | None]) -> None:
    st.subheader("JSON Preview")
    existing = [(name, path) for name, path in artifacts.items() if path is not None and path.exists()]
    if not existing:
        st.info("No JSON artifact is available for this run.")
        return
    name, path = existing[0]
    st.caption(f"Previewing {name}")
    content = read_json(path)
    if isinstance(content, list):
        st.json(content[:20])
        if len(content) > 20:
            st.caption(f"Showing first 20 of {len(content)} JSON items.")
    else:
        st.json(content)


if __name__ == "__main__":
    main()
