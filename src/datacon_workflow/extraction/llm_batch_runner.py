from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path
from typing import Callable

from datacon_workflow.domains.benzimidazoles import BenzimidazoleLLMRecord
from datacon_workflow.extraction.evidence_selector import BenzimidazoleEvidence
from datacon_workflow.extraction.llm_extractor import (
    LLMExtractionConfig,
    LLMExtractionResult,
    extract_benzimidazoles_with_llm,
)
from datacon_workflow.validation.llm_schema_validator import validate_llm_payload, validate_llm_records
from pdf_extraction.models import stable_pdf_stem


ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class BatchExtraction:
    result: LLMExtractionResult
    evidence: list[BenzimidazoleEvidence]
    batch_index: int
    batch_count: int


@dataclass(frozen=True)
class LLMRunResult:
    batches: list[BatchExtraction]
    records: list[BenzimidazoleLLMRecord]

    @property
    def status(self) -> str:
        return combined_status([batch.result for batch in self.batches])

    @property
    def warnings(self) -> list[str]:
        return [
            warning
            for batch in self.batches
            for warning in batch.result.warnings
        ] + [warning for record in self.records for warning in record.warnings]


def replay_path_for_pdf(replay_dir: Path | None, pdf_path: Path) -> Path | None:
    if replay_dir is None:
        return None
    path = replay_dir / f"{stable_pdf_stem(pdf_path)}.llm.json"
    return path if path.exists() else None


def run_llm_batches(
    evidence: list[BenzimidazoleEvidence],
    article_dir: Path,
    batch_size: int,
    replay_path: Path | None = None,
    max_concurrent_batches: int = 1,
    resume_existing_batches: bool = False,
    config: LLMExtractionConfig | None = None,
    progress: ProgressCallback | None = None,
) -> LLMRunResult:
    batches = _run_llm_extractions(
        evidence=evidence,
        article_dir=article_dir,
        batch_size=batch_size,
        replay_path=replay_path,
        max_concurrent_batches=max_concurrent_batches,
        resume_existing_batches=resume_existing_batches,
        config=config,
        progress=progress,
    )
    records: list[BenzimidazoleLLMRecord] = []
    for batch in batches:
        raw_payload = read_raw_payload(batch.result.raw_response_path)
        if raw_payload is not None:
            records.extend(validate_llm_payload(raw_payload, batch.evidence))
        else:
            records.extend(validate_llm_records(batch.result.records, batch.evidence))
    return LLMRunResult(batches=batches, records=records)


def combined_status(extractions: list[LLMExtractionResult]) -> str:
    statuses = {extraction.status for extraction in extractions}
    if statuses <= {"live", "cached_live"}:
        return "live"
    if statuses == {"disabled"}:
        return "disabled"
    if statuses <= {"replay", "cached_live"}:
        return "replay"
    if "live" in statuses:
        return "partial_live"
    if "llm_error" in statuses:
        return "llm_error"
    return ",".join(sorted(statuses))


def read_raw_payload(path: Path | None) -> list[dict[str, object]] | None:
    if path is None or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except JSONDecodeError:
        return None
    if isinstance(payload, dict):
        payload = payload.get("records")
    return payload if isinstance(payload, list) else None


def read_dedup_report(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def apply_evidence_slice(
    evidence: list[BenzimidazoleEvidence],
    slice_spec: str | None,
) -> list[BenzimidazoleEvidence]:
    if not slice_spec:
        return evidence
    start_text, separator, stop_text = slice_spec.partition(":")
    if not separator:
        raise ValueError("Evidence slice must use START:STOP syntax, for example 0:10 or 10:20.")
    start = int(start_text) if start_text else None
    stop = int(stop_text) if stop_text else None
    return evidence[slice(start, stop)]


def _run_llm_extractions(
    evidence: list[BenzimidazoleEvidence],
    article_dir: Path,
    batch_size: int,
    replay_path: Path | None,
    max_concurrent_batches: int = 1,
    resume_existing_batches: bool = False,
    config: LLMExtractionConfig | None = None,
    progress: ProgressCallback | None = None,
) -> list[BatchExtraction]:
    if replay_path is not None:
        result = extract_benzimidazoles_with_llm(evidence, article_dir, config=config, replay_path=replay_path)
        return [BatchExtraction(result=result, evidence=evidence, batch_index=1, batch_count=1)]

    batch_size = max(1, batch_size)
    evidence_batches = [evidence[index:index + batch_size] for index in range(0, len(evidence), batch_size)] or [[]]
    batch_root = article_dir / "llm_batches"
    max_concurrent_batches = max(1, max_concurrent_batches)
    indexed_batches = list(enumerate(evidence_batches, start=1))
    batch_count = len(indexed_batches)

    if max_concurrent_batches > 1:
        completed: dict[int, BatchExtraction] = {}
        with ThreadPoolExecutor(max_workers=max_concurrent_batches) as executor:
            futures = {}
            for batch_index, batch in indexed_batches:
                batch_dir = batch_root / f"batch_{batch_index:03d}"
                cached = _cached_batch_result(batch_dir) if resume_existing_batches else None
                if cached is not None:
                    _emit(progress, _batch_message(batch_index, batch_count, batch, "cached", batch_dir))
                    completed[batch_index] = BatchExtraction(cached, batch, batch_index, batch_count)
                    continue
                _emit(progress, _batch_message(batch_index, batch_count, batch, "submitted", batch_dir))
                futures[
                    executor.submit(
                        _timed_extract,
                        extract_benzimidazoles_with_llm,
                        batch,
                        batch_dir,
                        config,
                    )
                ] = (batch_index, batch)
            for future in as_completed(futures):
                batch_index, batch = futures[future]
                result, elapsed_seconds = future.result()
                completed[batch_index] = BatchExtraction(result, batch, batch_index, batch_count)
                _emit(
                    progress,
                    _batch_message(
                        batch_index,
                        batch_count,
                        batch,
                        f"completed status={result.status} records={len(result.records)} elapsed={elapsed_seconds:.1f}s",
                        batch_dir=batch_root / f"batch_{batch_index:03d}",
                    ),
                )
        return [completed[batch_index] for batch_index, _batch in indexed_batches]

    results: list[BatchExtraction] = []
    for batch_index, batch in indexed_batches:
        batch_dir = batch_root / f"batch_{batch_index:03d}"
        cached = _cached_batch_result(batch_dir) if resume_existing_batches else None
        if cached is not None:
            _emit(progress, _batch_message(batch_index, batch_count, batch, "cached", batch_dir))
            results.append(BatchExtraction(cached, batch, batch_index, batch_count))
            continue
        _emit(progress, _batch_message(batch_index, batch_count, batch, "starting", batch_dir))
        result, elapsed_seconds = _timed_extract(extract_benzimidazoles_with_llm, batch, batch_dir, config)
        _emit(
            progress,
            _batch_message(
                batch_index,
                batch_count,
                batch,
                f"completed status={result.status} records={len(result.records)} elapsed={elapsed_seconds:.1f}s",
                batch_dir,
            ),
        )
        results.append(BatchExtraction(result, batch, batch_index, batch_count))
    return results


def _cached_batch_result(batch_dir: Path) -> LLMExtractionResult | None:
    raw_response_path = batch_dir / "llm_raw_response.json"
    payload = read_raw_payload(raw_response_path)
    if payload is None:
        return None
    return LLMExtractionResult(
        records=[],
        status="cached_live",
        warnings=[],
        raw_response_path=raw_response_path,
    )


def _emit(progress: ProgressCallback | None, message: str) -> None:
    if progress is not None:
        progress(message)


def _timed_extract(
    extractor: Callable[..., LLMExtractionResult],
    evidence: list[BenzimidazoleEvidence],
    batch_dir: Path,
    config: LLMExtractionConfig | None,
) -> tuple[LLMExtractionResult, float]:
    started = time.perf_counter()
    result = extractor(evidence, batch_dir, config=config)
    return result, time.perf_counter() - started


def _batch_message(
    batch_index: int,
    batch_count: int,
    evidence: list[BenzimidazoleEvidence],
    status: str,
    batch_dir: Path,
) -> str:
    evidence_ids = ", ".join(item.evidence_id for item in evidence[:4])
    if len(evidence) > 4:
        evidence_ids += f", +{len(evidence) - 4} more"
    evidence_ids = evidence_ids or "none"
    pages = sorted({item.page for item in evidence if item.page is not None})
    page_text = ",".join(str(page) for page in pages[:6]) if pages else "unknown"
    if len(pages) > 6:
        page_text += ",..."
    return (
        f"batch {batch_index}/{batch_count}: {status}; "
        f"chunks={len(evidence)} pages={page_text} evidence=[{evidence_ids}] "
        f"dir={batch_dir}"
    )
