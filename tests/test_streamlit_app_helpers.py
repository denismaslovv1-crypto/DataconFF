from __future__ import annotations

import csv
import json
from pathlib import Path

from app import (
    DEFAULT_DOMAIN_KEY,
    DOMAIN_CONFIGS,
    SYNERGY_SINGLE_ARTICLE_DISABLED_MESSAGE,
    article_display_rows,
    available_saved_result_options,
    available_result_dirs,
    display_synergy_single_article_command,
    display_full_run_command,
    field_metric_display_rows,
    full_run_command,
    is_public_result_dir,
    load_full_run,
    normalize_article_output_dirs,
    output_dir_for,
    public_article_display_rows,
    render_single_article,
    result_context,
    safe_stem,
    saved_result_option_path,
    single_output_dir_for,
    synergy_single_article_command,
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


def test_public_article_display_uses_article_macro_f1() -> None:
    rows = article_display_rows(
        [
            {"pdf": "synergy.pdf", "pred_rows": "0", "gt_rows": "24", "macro_f1": "0.362611", "status": "ok"},
        ]
    )

    public_rows = public_article_display_rows(rows)

    assert public_rows[0]["Macro-F1"] == "0.3626"


def test_available_result_dirs_require_metrics_json(tmp_path: Path) -> None:
    (tmp_path / "good").mkdir()
    (tmp_path / "good" / "metrics.json").write_text("{}", encoding="utf-8")
    (tmp_path / "old_rules_complete").mkdir()
    (tmp_path / "old_rules_complete" / "metrics.json").write_text("{}", encoding="utf-8")
    (tmp_path / "missing").mkdir()

    assert available_result_dirs(tmp_path) == [tmp_path / "good"]
    assert not is_public_result_dir(tmp_path / "old_rules_complete")


def test_synergy_saved_result_options_are_domain_scoped(tmp_path: Path) -> None:
    good = tmp_path / "benzimidazoles_full"
    good.mkdir()
    (good / "metrics.json").write_text("{}", encoding="utf-8")
    extra = tmp_path / "benzimidazoles_refactor_check"
    extra.mkdir()
    (extra / "metrics.json").write_text("{}", encoding="utf-8")
    synergy = tmp_path / "synergy_full"
    synergy.mkdir()
    (synergy / "metrics.json").write_text("{}", encoding="utf-8")
    old_synergy = tmp_path / "synergy_old"
    old_synergy.mkdir()
    (old_synergy / "metrics.json").write_text("{}", encoding="utf-8")

    options = available_saved_result_options(tmp_path, "synergy")

    assert any(option.endswith("synergy_full") for option in options)
    assert not any(option.endswith("benzimidazoles_full") for option in options)
    assert not any(option.endswith("benzimidazoles_refactor_check") for option in options)
    assert not any(option.endswith("synergy_old") for option in options)
    assert saved_result_option_path(str(synergy)) == synergy


def test_benzimidazoles_saved_result_options_are_domain_scoped(tmp_path: Path) -> None:
    benz = tmp_path / "benzimidazoles_full"
    benz.mkdir()
    (benz / "metrics.json").write_text("{}", encoding="utf-8")
    benz_extra = tmp_path / "benzimidazoles_refactor_check"
    benz_extra.mkdir()
    (benz_extra / "metrics.json").write_text("{}", encoding="utf-8")
    synergy = tmp_path / "synergy_full"
    synergy.mkdir()
    (synergy / "metrics.json").write_text("{}", encoding="utf-8")

    options = available_saved_result_options(tmp_path, "benzimidazoles")

    assert any(option.endswith("benzimidazoles_full") for option in options)
    assert any(option.endswith("benzimidazoles_refactor_check") for option in options)
    assert not any(option.endswith("synergy_full") for option in options)


def test_missing_synergy_saved_result_is_ignored(tmp_path: Path) -> None:
    good = tmp_path / "benzimidazoles_full"
    good.mkdir()
    (good / "metrics.json").write_text("{}", encoding="utf-8")

    options = available_saved_result_options(tmp_path, "synergy")

    assert "synergy_full" not in options


def test_result_context_keeps_benzimidazoles_default() -> None:
    context = result_context(Path("outputs/benzimidazoles_full"))
    assert context["domain"] == "Benzimidazoles"
    assert context["baseline"] == 0.217
    assert DEFAULT_DOMAIN_KEY == "benzimidazoles"


def test_result_context_selects_synergy_baseline() -> None:
    context = result_context(Path("outputs/synergy_full"), "synergy")
    assert context["domain"] == "Synergy"
    assert context["baseline"] == 0.080


def test_domain_saved_result_defaults() -> None:
    assert DOMAIN_CONFIGS["benzimidazoles"].output_label == "outputs/benzimidazoles_full"
    assert DOMAIN_CONFIGS["synergy"].output_label == "outputs/synergy_full"


def test_field_metric_display_rows_rounds_metric_columns() -> None:
    rows = field_metric_display_rows(
        [
            {
                "field": "bacteria",
                "precision": "0.345",
                "recall": 0.994,
                "f1": "1",
                "true_positive": "12",
            }
        ]
    )

    assert rows == [
        {
            "field": "bacteria",
            "precision": "0.34",
            "recall": "0.99",
            "f1": "1.00",
            "true_positive": "12",
        }
    ]


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
    assert "--llm-mode" not in command
    assert display_full_run_command(Path("pdfs"), Path("ground_truth.csv"), Path("outputs/benzimidazoles_full")) == (
        ".\\.venv\\Scripts\\python.exe scripts/run_benzimidazoles_full.py "
        "--pdf-dir pdfs --ground-truth ground_truth.csv "
        "--output-dir outputs/benzimidazoles_full"
    )


def test_full_run_command_changes_by_domain() -> None:
    benz_command = display_full_run_command(
        Path("data/chemx/benzimidazoles/pdfs"),
        Path("data/chemx/benzimidazoles/ground_truth.csv"),
        Path("outputs/benzimidazoles_full"),
        "benzimidazoles",
    )
    synergy_command = display_full_run_command(
        Path("data/chemx/synergy/pdfs"),
        Path("data/chemx/synergy/ground_truth.csv"),
        Path("outputs/synergy_full"),
        "synergy",
    )

    assert "scripts/run_benzimidazoles_full.py" in benz_command
    assert "--pdf-dir data/chemx/benzimidazoles/pdfs" in benz_command
    assert "scripts/run_synergy_experimental.py" in synergy_command
    assert "--pdf-dir data/chemx/synergy/pdfs" in synergy_command
    assert "--output-dir outputs/synergy_full" in synergy_command


def test_single_article_domain_support_is_explicit() -> None:
    assert DOMAIN_CONFIGS["benzimidazoles"].single_article_enabled is True
    assert DOMAIN_CONFIGS["benzimidazoles"].ground_truth_csv.as_posix().endswith(
        "data/chemx/benzimidazoles/ground_truth.csv"
    )
    assert DOMAIN_CONFIGS["synergy"].single_article_enabled is True
    assert DOMAIN_CONFIGS["synergy"].pdf_dir.as_posix().endswith("data/chemx/synergy/pdfs")
    assert DOMAIN_CONFIGS["synergy"].ground_truth_csv.as_posix().endswith("data/chemx/synergy/ground_truth.csv")


def test_synergy_single_article_no_disabled_message(monkeypatch, tmp_path: Path) -> None:
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    (pdf_dir / "synergy.pdf").write_bytes(b"%PDF")
    synergy_config = DOMAIN_CONFIGS["synergy"]
    patched = type(synergy_config)(
        key=synergy_config.key,
        label=synergy_config.label,
        short_name=synergy_config.short_name,
        pdf_dir=pdf_dir,
        ground_truth_csv=synergy_config.ground_truth_csv,
        output_dir=synergy_config.output_dir,
        output_label=synergy_config.output_label,
        runner_script=synergy_config.runner_script,
        baseline_macro_f1=synergy_config.baseline_macro_f1,
        single_article_enabled=synergy_config.single_article_enabled,
    )
    monkeypatch.setitem(DOMAIN_CONFIGS, "synergy", patched)
    fake_st = _FakeSingleArticleStreamlit("Additional: Synergy")

    render_single_article(fake_st)

    assert SYNERGY_SINGLE_ARTICLE_DISABLED_MESSAGE not in fake_st.messages
    assert fake_st.selected_pdfs == ["synergy.pdf"]


def test_synergy_single_article_command_uses_pdf_runner() -> None:
    command = synergy_single_article_command(
        Path("data/chemx/synergy/pdfs/synergy.pdf"),
        Path("data/chemx/synergy/ground_truth.csv"),
        Path("outputs/synergy_single/synergy"),
    )

    assert command[0].endswith(".venv\\Scripts\\python.exe")
    assert command[1].endswith("scripts\\run_synergy_experimental.py")
    assert "--pdf" in command
    assert "--pdf-dir" not in command
    assert "scripts/run_synergy_experimental.py" in display_synergy_single_article_command(
        Path("data/chemx/synergy/pdfs/synergy.pdf"),
        Path("data/chemx/synergy/ground_truth.csv"),
        Path("outputs/synergy_single/synergy"),
    )
    assert single_output_dir_for(Path("synergy.pdf"), DOMAIN_CONFIGS["synergy"]).as_posix().endswith(
        "outputs/synergy_single/synergy"
    )


class _FakeSingleArticleStreamlit:
    def __init__(self, domain_label: str) -> None:
        self.domain_label = domain_label
        self.messages: list[str] = []
        self.selected_pdfs: list[str] = []

    def selectbox(self, label: str, options: list[str], index: int = 0, key: str = "") -> str:
        if label == "Domain":
            assert self.domain_label in options
            return self.domain_label
        if label == "Bundled PDF":
            self.selected_pdfs.append(options[index])
            return options[index]
        raise AssertionError(label)

    def markdown(self, message: str) -> None:
        self.messages.append(message)

    def warning(self, message: str) -> None:
        self.messages.append(message)

    def info(self, message: str) -> None:
        self.messages.append(message)

    def file_uploader(self, *_args, **_kwargs) -> None:
        return None

    def text_input(self, _label: str, value: str, key: str) -> str:
        return value

    def caption(self, message: str) -> None:
        self.messages.append(message)

    def code(self, _body: str, language: str) -> None:
        return None

    def button(self, *_args, **_kwargs) -> bool:
        return False


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
