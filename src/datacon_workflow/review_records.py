from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from datacon_workflow.domains.benzimidazoles import CHEMX_COLUMNS


NOT_AVAILABLE = "not available"

REVIEW_COLUMNS = (
    "pdf",
    "article_id",
    *CHEMX_COLUMNS,
    "page",
    "evidence_id",
    "source_kind",
    "source_text",
    "compound_mention",
    "compound_label_found",
    "extractor",
    "confidence",
    "raw_value",
    "raw_units",
    "normalized_value",
    "normalized_units",
    "duplicate_status",
    "duplicate_count",
    "value_mismatch",
)


def build_review_records(output_dir: Path, article_id: str | None = None) -> list[dict[str, str]]:
    records = _load_prediction_records(output_dir)
    article = article_id or _article_id(output_dir)
    review_rows: list[dict[str, str]] = []
    for index, item in enumerate(records, start=1):
        record = item.get("record", {})
        evidence = item.get("evidence") or {}
        evidence_id = str(item.get("evidence_id") or record.get("evidence_id") or "")
        if not evidence_id:
            evidence_id = stable_evidence_id(evidence) if evidence else f"row:{index}"
        source_text = _text_from_evidence(evidence)
        source_snippet = _source_snippet(source_text, _clean(record.get("compound_id")), _clean(record.get("target_value")))
        source_kind = _source_kind(evidence)
        compound_id = _clean(record.get("compound_id"))
        mention = detect_compound_mention(compound_id, source_text)
        target_value = _clean(record.get("target_value"))
        target_units = _clean(record.get("target_units"))
        raw_value = _raw_value(record, target_value)
        raw_units = _raw_units(record, target_units)
        review_rows.append(
            {
                "pdf": _clean(evidence.get("source_file")) or article,
                "article_id": article,
                "compound_id": compound_id,
                "smiles": _clean(record.get("smiles")),
                "target_type": _clean(record.get("target_type")),
                "target_relation": _clean(record.get("target_relation")),
                "target_value": target_value,
                "target_units": target_units,
                "bacteria": _clean(record.get("bacteria")),
                "page": _clean(evidence.get("page")),
                "evidence_id": evidence_id,
                "source_kind": source_kind,
                "source_text": source_snippet or NOT_AVAILABLE,
                "compound_mention": mention,
                "compound_label_found": "yes" if mention != NOT_AVAILABLE else "no",
                "extractor": _clean(evidence.get("extraction_method")) or NOT_AVAILABLE,
                "confidence": _clean(evidence.get("confidence")) or NOT_AVAILABLE,
                "raw_value": raw_value,
                "raw_units": raw_units,
                "normalized_value": target_value,
                "normalized_units": target_units,
                "duplicate_status": "unique",
                "duplicate_count": "1",
                "value_mismatch": "no",
            }
        )
    return mark_duplicate_status(review_rows)


def write_review_records(output_dir: Path, article_id: str | None = None) -> tuple[Path, Path]:
    rows = build_review_records(output_dir, article_id)
    json_path = output_dir / "review_records.json"
    csv_path = output_dir / "review_records.csv"
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    write_review_records_csv(rows, csv_path)
    return csv_path, json_path


def write_review_records_csv(rows: list[dict[str, str]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


def merge_review_records(output_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(output_dir.glob("*/review_records.json"), key=lambda item: str(item).lower()):
        payload = _read_json(path)
        if isinstance(payload, list):
            rows.extend(_stringify_row(row) for row in payload if isinstance(row, dict))
    if rows:
        (output_dir / "review_records.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        write_review_records_csv(rows, output_dir / "review_records.csv")
    return rows


def duplicate_diagnostics(rows: list[dict[str, str]]) -> dict[str, Any]:
    chemx_counts = Counter(_chemx_key(row) for row in rows)
    same_evidence_counts = Counter((_chemx_key(row), row.get("evidence_id", ""), row.get("source_text", "")) for row in rows)
    evidence_by_chemx: dict[tuple[str, ...], set[str]] = defaultdict(set)
    mismatch_examples: list[dict[str, str]] = []
    for row in rows:
        evidence_by_chemx[_chemx_key(row)].add(row.get("evidence_id", ""))
        if row.get("value_mismatch") == "yes":
            mismatch_examples.append(row)
    return {
        "exact_duplicate_chemx_rows": sum(count - 1 for count in chemx_counts.values() if count > 1),
        "duplicates_with_same_evidence_id": sum(count - 1 for count in same_evidence_counts.values() if count > 1),
        "repeated_mentions_with_different_evidence_id": sum(
            chemx_counts[key] for key, evidence_ids in evidence_by_chemx.items() if len(evidence_ids) > 1
        ),
        "mismatch_examples": mismatch_examples[:20],
    }


def mark_duplicate_status(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    chemx_counts = Counter(_chemx_key(row) for row in rows)
    same_evidence_counts = Counter((_chemx_key(row), row.get("evidence_id", ""), row.get("source_text", "")) for row in rows)
    evidence_by_chemx: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for row in rows:
        evidence_by_chemx[_chemx_key(row)].add(row.get("evidence_id", ""))
    updated: list[dict[str, str]] = []
    for row in rows:
        row = dict(row)
        chemx_key = _chemx_key(row)
        same_evidence_key = (chemx_key, row.get("evidence_id", ""), row.get("source_text", ""))
        row["duplicate_count"] = str(chemx_counts[chemx_key])
        if same_evidence_counts[same_evidence_key] > 1:
            row["duplicate_status"] = "duplicate_same_evidence"
        elif chemx_counts[chemx_key] > 1 and len(evidence_by_chemx[chemx_key]) > 1:
            row["duplicate_status"] = "repeated_distinct_evidence"
        elif chemx_counts[chemx_key] > 1:
            row["duplicate_status"] = "duplicate_chemx_row"
        else:
            row["duplicate_status"] = "unique"
        updated.append(row)
    return updated


def stable_evidence_id(evidence: dict[str, Any]) -> str:
    pieces = [
        _clean(evidence.get("source_file")),
        _clean(evidence.get("page")),
        _clean(evidence.get("section")),
        _clean(evidence.get("table_id")),
        _clean(evidence.get("row_id")),
        _text_from_evidence(evidence),
    ]
    digest = hashlib.sha1("|".join(pieces).encode("utf-8")).hexdigest()
    return f"ev:{digest[:12]}"


def detect_compound_mention(compound_id: str, source_text: str) -> str:
    label = str(compound_id or "").strip()
    text = str(source_text or "")
    if not label or label == "NOT_DETECTED" or not text:
        return NOT_AVAILABLE
    table_mention = _table_first_cell_mention(label, text)
    if table_mention:
        return table_mention
    ranges = _range_mentions(label, text)
    if ranges != NOT_AVAILABLE:
        return ranges
    label_pattern = _label_pattern(label)
    patterns = [
        rf"\bbenzimidazole\s+derivative\s*\(?\s*{label_pattern}\s*\)?",
        rf"\bderivative\s*\(?\s*{label_pattern}\s*\)?",
        rf"\bcompounds?\s+(?:no\.?\s*)?\(?\s*{label_pattern}\s*\)?",
        rf"\bseries\s+{label_pattern}\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return _clean_space(match.group(0))
    return NOT_AVAILABLE


def json_preview_artifacts(artifacts: dict[str, Path | None]) -> list[tuple[str, Path]]:
    priority = (
        "review_records.json",
        "predictions_with_evidence.json",
        "predictions.json",
        "run_manifest.json",
        "metrics.json",
    )
    existing: list[tuple[str, Path]] = []
    for name in priority:
        path = artifacts.get(name)
        if path is not None and path.exists():
            existing.append((name, path))
    seen = {name for name, _path in existing}
    for name, path in artifacts.items():
        if name not in seen and path is not None and path.exists() and path.suffix == ".json":
            existing.append((name, path))
    return existing


def _load_prediction_records(output_dir: Path) -> list[dict[str, Any]]:
    sidecar_path = output_dir / "predictions_with_evidence.json"
    rules_json_path = output_dir / "rules" / "predictions.json"
    predictions_json_path = output_dir / "predictions.json"
    if sidecar_path.exists():
        sidecar = _read_json(sidecar_path)
        rules_records = _read_json(rules_json_path) if rules_json_path.exists() else []
        if isinstance(sidecar, list):
            return [_from_sidecar_item(item, index, rules_records) for index, item in enumerate(sidecar, start=1)]
    payload = _read_json(predictions_json_path)
    if isinstance(payload, list):
        return [{"record": item, "evidence": item.get("evidence") if isinstance(item, dict) else {}} for item in payload if isinstance(item, dict)]
    payload = _read_json(rules_json_path)
    if isinstance(payload, list):
        return [{"record": item, "evidence": item.get("evidence") if isinstance(item, dict) else {}} for item in payload if isinstance(item, dict)]
    return []


def _from_sidecar_item(item: Any, index: int, rules_records: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"record": {}, "evidence": {}, "evidence_id": f"row:{index}"}
    record = item.get("record") if isinstance(item.get("record"), dict) else {}
    evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
    evidence_id = _clean(record.get("evidence_id")) or f"rule-{index}"
    if not evidence and evidence_id.startswith("rule-") and isinstance(rules_records, list):
        rule_index = _rule_index(evidence_id)
        if rule_index is not None and 0 <= rule_index < len(rules_records):
            rule_record = rules_records[rule_index]
            if isinstance(rule_record, dict):
                evidence = rule_record.get("evidence") if isinstance(rule_record.get("evidence"), dict) else {}
    if not evidence:
        merged = item.get("merged_evidence")
        if isinstance(merged, list) and merged and isinstance(merged[0], dict):
            evidence = merged[0]
    return {"record": record, "evidence": evidence, "evidence_id": evidence_id}


def _rule_index(evidence_id: str) -> int | None:
    match = re.fullmatch(r"rule-(\d+)", evidence_id)
    return int(match.group(1)) - 1 if match else None


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _article_id(output_dir: Path) -> str:
    return output_dir.name


def _text_from_evidence(evidence: dict[str, Any]) -> str:
    return _clean(evidence.get("evidence_text") or evidence.get("text"))


def _source_snippet(source_text: str, compound_id: str, target_value: str, limit: int = 1200) -> str:
    text = _clean_space(source_text)
    if len(text) <= limit:
        return text
    anchors = [value for value in (compound_id, target_value) if value and value != "NOT_DETECTED"]
    positions = [text.lower().find(anchor.lower()) for anchor in anchors]
    positions = [position for position in positions if position >= 0]
    center = positions[0] if positions else 0
    start = max(0, center - limit // 3)
    end = min(len(text), start + limit)
    start = max(0, end - limit)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = f"...{snippet}"
    if end < len(text):
        snippet = f"{snippet}..."
    return snippet


def _source_kind(evidence: dict[str, Any]) -> str:
    row_id = _clean(evidence.get("row_id"))
    table_id = _clean(evidence.get("table_id"))
    if row_id == "table_like_text" or table_id == "table_like_text":
        return "table_like_text"
    if table_id:
        return "table"
    return "text" if _text_from_evidence(evidence) else NOT_AVAILABLE


def _raw_value(record: dict[str, Any], normalized: str) -> str:
    for key in ("raw_value", "source_value"):
        value = _clean(record.get(key))
        if value:
            return value
    return NOT_AVAILABLE if not normalized else normalized


def _raw_units(record: dict[str, Any], normalized: str) -> str:
    for key in ("raw_units", "source_units"):
        value = _clean(record.get(key))
        if value:
            return value
    return NOT_AVAILABLE if not normalized else normalized


def _chemx_key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(row.get(column, "") for column in CHEMX_COLUMNS)


def _stringify_row(row: dict[str, Any]) -> dict[str, str]:
    return {key: _clean(value) for key, value in row.items()}


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _clean_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _label_pattern(label: str) -> str:
    pieces = [re.escape(piece) for piece in re.split(r"[-–—]", label)]
    return r"[-–—]".join(pieces)


def _normalized_label(value: str) -> str:
    return value.strip().lower().replace("–", "-").replace("—", "-")


def _table_first_cell_mention(label: str, text: str) -> str | None:
    normalized = _normalized_label(label)
    for line in text.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        first = re.split(r"\s+|\|", cleaned, maxsplit=1)[0].strip("()[],:;")
        if _normalized_label(first) == normalized:
            return first
    return None


def _range_mentions(label: str, text: str) -> str:
    label_match = re.fullmatch(r"(\d+)([A-Za-z])", label.strip())
    if not label_match:
        return NOT_AVAILABLE
    number, letter = label_match.group(1), label_match.group(2).lower()
    pattern = rf"\bcompounds?\s+{re.escape(number)}([A-Za-z])\s*[-–—]\s*{re.escape(number)}([A-Za-z])\b"
    for match in re.finditer(pattern, text, flags=re.I):
        start = match.group(1).lower()
        end = match.group(2).lower()
        if ord(start) <= ord(letter) <= ord(end):
            return _clean_space(match.group(0))
    return NOT_AVAILABLE
