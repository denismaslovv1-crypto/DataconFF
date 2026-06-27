from __future__ import annotations

import csv
import json
from pathlib import Path

from app import (
    article_display_rows,
    available_result_dirs,
    display_full_run_command,
    full_run_command,
    is_public_result_dir,
    load_full_run,
    normalize_article_output_dirs,
    output_dir_for,
    public_article_display_rows,
    safe_stem,
    zero_row_articles,
)
from datacon_workflow.domains.benzimidazoles import CHEMX_COLUMNS


def test_safe_stem_removes_path_and_ui_unsafe_characters() -> None:
    assert safe_stem("Janupally 2014 (final).pdf") == "Janupally_2014_final_"
    assert safe_stem("..\\article.pdf") == "article"


def test_output_dir_is_under_requested_ui_root(tmp_path: Path) -> None:
    output_dir = output_dir_for(Path("Janupally 2014.pdf"), tmp_path)
    assert output_dir == tmp_path / "Janupally_2014"


def test_load_full_run_reads_required_artifacts(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    output_dir.mkdir()
    (output_dir / "metrics.json").write_text(
        json.dumps({"macro_f1": 0.5, "prediction_count": 1, "ground_truth_count": 2}),
        encoding="utf-8",
    )
    _write_csv(output_dir / "field_metrics.csv", ["field", "f1"], [{"field": "bacteria", "f1": "1"}])
    _write_csv(
        output_dir / "article_summary.csv",
        ["pdf", "pred_rows", "gt_rows", "macro_f1", "status"],
        [{"pdf": "article.pdf", "pred_rows": "0", "gt_rows": "2", "macro_f1": "0", "status": "ok"}],
    )
    _write_csv(
        output_dir / "predictions.csv",
        list(CHEMX_COLUMNS),
        [
            {
                "compound_id": "5a",
                "smiles": "NOT_DETECTED",
                "target_type": "MIC",
                "target_relation": "=",
                "target_value": "4",
                "target_units": "µg/mL",
                "bacteria": "S. aureus",
            }
        ],
    )

    loaded = load_full_run(output_dir)

    assert loaded["metrics"]["macro_f1"] == 0.5
    assert loaded["field_metrics"][0]["field"] == "bacteria"
    assert loaded["article_summary"][0]["gt_rows"] == "2"
    assert loaded["predictions"][0]["compound_id"] == "5a"
    assert loaded["review_records"] == []


def test_article_display_flags_zero_and_low_rows() -> None:
    rows = article_display_rows(
        [
            {"pdf": "zero.pdf", "pred_rows": "0", "gt_rows": "24", "macro_f1": "0", "status": "ok"},
            {"pdf": "low.pdf", "pred_rows": "2", "gt_rows": "20", "macro_f1": "0.1", "status": "ok"},
            {"pdf": "fine.pdf", "pred_rows": "8", "gt_rows": "8", "macro_f1": "1", "status": "ok"},
        ]
    )

    assert rows[0]["flags"] == "zero rows"
    assert rows[1]["flags"] == "low rows"
    assert rows[2]["flags"] == ""
    assert "flags" not in public_article_display_rows(rows)[0]
    assert zero_row_articles(
        [{"pdf": "zero.pdf", "pred_rows": "0", "gt_rows": "24", "status": "ok"}]
    )[0]["gt_rows"] == 24


def test_available_result_dirs_require_metrics_json(tmp_path: Path) -> None:
    (tmp_path / "good").mkdir()
    (tmp_path / "good" / "metrics.json").write_text("{}", encoding="utf-8")
    (tmp_path / "old_rules_complete").mkdir()
    (tmp_path / "old_rules_complete" / "metrics.json").write_text("{}", encoding="utf-8")
    (tmp_path / "missing").mkdir()

    assert available_result_dirs(tmp_path) == [tmp_path / "good"]
    assert not is_public_result_dir(tmp_path / "old_rules_complete")


def test_article_output_dirs_are_corrected_to_loaded_run(tmp_path: Path) -> None:
    output_dir = tmp_path / "benzimidazoles_full"
    article_dir = output_dir / "jhet.3467"
    article_dir.mkdir(parents=True)

    rows = normalize_article_output_dirs(
        [
            {
                "pdf": "data\\chemx\\benzimidazoles\\pdfs\\jhet.3467.pdf",
                "output_dir": "outputs\\benzimidazoles_full_dedup_fix\\jhet.3467",
            }
        ],
        output_dir,
    )

    assert rows[0]["output_dir"] == str(article_dir)


def test_full_run_command_is_rules_only_repo_python(tmp_path: Path) -> None:
    command = full_run_command(tmp_path / "pdfs", tmp_path / "ground_truth.csv", tmp_path / "out")

    assert command[0].endswith(".venv\\Scripts\\python.exe")
    assert command[-2:] == ["--llm-mode", "never"]
    assert display_full_run_command(Path("pdfs"), Path("ground_truth.csv"), Path("outputs/benzimidazoles_full")) == (
        ".\\.venv\\Scripts\\python.exe scripts/run_benzimidazoles_full.py "
        "--pdf-dir pdfs --ground-truth ground_truth.csv "
        "--output-dir outputs/benzimidazoles_full --llm-mode never"
    )


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
