from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from datacon_workflow.domains.benzimidazoles import BenzimidazoleLLMRecord, BenzimidazoleRawRecord, EvidenceProvenance
from datacon_workflow.extraction.evidence_selector import BenzimidazoleEvidence
from datacon_workflow.extraction.evidence_builder import EvidenceChunk


def parse_llm_json_array(response: str, chunk: EvidenceChunk) -> list[BenzimidazoleRawRecord]:
    """Validate a JSON-only LLM response against the evidence chunk it was given.

    This module intentionally has no network client: model choice and credentials remain
    outside the deterministic workflow.
    """
    payload = json.loads(response)
    if not isinstance(payload, list):
        raise ValueError("LLM response must be a JSON array")
    records: list[BenzimidazoleRawRecord] = []
    for item in payload:
        try:
            candidate = BenzimidazoleRawRecord.model_validate({
                **item,
                "evidence": EvidenceProvenance(
                    source_file=chunk.source.source_file,
                    page=chunk.source.page,
                    section=chunk.source.section,
                    table_id=chunk.source.table_id,
                    row_id=chunk.row_id,
                    evidence_text=chunk.text,
                    extraction_method="benzimidazole.llm_evidence_only",
                    confidence=0.4,
                ),
            })
        except ValidationError as exc:
            raise ValueError(f"Unsupported LLM record: {exc}") from exc
        if not candidate.target_value or candidate.target_value not in chunk.text:
            raise ValueError("LLM record target_value is not supported by its evidence chunk")
        records.append(candidate)
    return records


@dataclass(frozen=True)
class LLMExtractionConfig:
    provider: str | None = None
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    api_type: str | None = None
    max_output_tokens: int | None = None

    @classmethod
    def from_env(cls) -> "LLMExtractionConfig":
        _load_project_dotenv()
        api_key_env = os.getenv("CHEMX_LLM_API_KEY_ENV") or os.getenv("EXTRACTION_AGENT_API_KEY_ENV")
        api_key = (
            os.getenv("CHEMX_LLM_API_KEY")
            or (os.getenv(api_key_env) if api_key_env else None)
            or os.getenv("OPENMODEL_API_KEY")
            or os.getenv("OPENAI_API_KEY")
        )
        provider = os.getenv("CHEMX_LLM_PROVIDER") or os.getenv("EXTRACTION_AGENT_PROVIDER") or os.getenv("OPENAI_PROVIDER")
        return cls(
            provider=provider,
            model=os.getenv("CHEMX_LLM_MODEL") or os.getenv("EXTRACTION_AGENT_MODEL") or os.getenv("OPENAI_MODEL"),
            api_key=api_key,
            base_url=os.getenv("CHEMX_LLM_BASE_URL") or os.getenv("EXTRACTION_AGENT_BASE_URL") or os.getenv("OPENAI_BASE_URL"),
            api_type=(
                os.getenv("CHEMX_LLM_API_TYPE")
                or os.getenv("EXTRACTION_AGENT_API_TYPE")
                or ("anthropic_messages" if provider == "openmodel" else "chat")
            ),
            max_output_tokens=_optional_int(
                os.getenv("CHEMX_LLM_MAX_OUTPUT_TOKENS") or os.getenv("EXTRACTION_AGENT_MAX_OUTPUT_TOKENS")
            ),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.model and self.api_key and self.api_key != "replace_me")


@dataclass(frozen=True)
class LLMExtractionResult:
    records: list[BenzimidazoleLLMRecord]
    status: str
    warnings: list[str]
    raw_response_path: Path | None = None


def extract_benzimidazoles_with_llm(
    evidence: list[BenzimidazoleEvidence],
    output_dir: Path,
    config: LLMExtractionConfig | None = None,
    replay_path: Path | None = None,
) -> LLMExtractionResult:
    """Extract ChemX records from selected evidence.

    Live calls require explicit env/config. Without config, the function writes
    an empty artifact and returns ``disabled`` rather than silently using a
    system default or a prepared prediction file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_response_path = output_dir / "llm_raw_response.json"
    if replay_path is not None:
        response = replay_path.read_text(encoding="utf-8")
        raw_response_path.write_text(response, encoding="utf-8")
        return _records_from_response(response, raw_response_path, status="replay")

    config = config or LLMExtractionConfig.from_env()
    if not config.is_configured:
        raw_response_path.write_text("[]\n", encoding="utf-8")
        return LLMExtractionResult(
            records=[],
            status="disabled",
            warnings=["LLM extraction disabled: set CHEMX_LLM_MODEL and CHEMX_LLM_API_KEY or pass a replay response."],
            raw_response_path=raw_response_path,
        )

    try:
        response = _call_openai_compatible_model(config, _build_benzimidazoles_prompt(evidence))
    except Exception as exc:  # noqa: BLE001 - provider errors must become run artifacts, not tracebacks.
        error_path = output_dir / "llm_error.json"
        warning = _provider_error_message(config, exc)
        error_path.write_text(json.dumps({"error": warning}, ensure_ascii=False, indent=2), encoding="utf-8")
        raw_response_path.write_text("[]\n", encoding="utf-8")
        return LLMExtractionResult(
            records=[],
            status="llm_error",
            warnings=[warning],
            raw_response_path=raw_response_path,
        )
    raw_response_path.write_text(response, encoding="utf-8")
    return _records_from_response(response, raw_response_path, status="live")


def _records_from_response(response: str, raw_response_path: Path, status: str) -> LLMExtractionResult:
    try:
        payload = json.loads(response)
    except json.JSONDecodeError as exc:
        return LLMExtractionResult([], status, [f"Invalid JSON response: {exc}"], raw_response_path)
    if isinstance(payload, dict) and "records" in payload:
        payload = payload["records"]
    if not isinstance(payload, list):
        return LLMExtractionResult([], status, ["LLM response must be a JSON array."], raw_response_path)
    records: list[BenzimidazoleLLMRecord] = []
    warnings: list[str] = []
    for index, item in enumerate(payload):
        try:
            records.append(BenzimidazoleLLMRecord.model_validate(item))
        except ValidationError as exc:
            warnings.append(f"record {index}: {exc}")
    return LLMExtractionResult(records, status, warnings, raw_response_path)


def _build_benzimidazoles_prompt(evidence: list[BenzimidazoleEvidence]) -> str:
    evidence_payload = [item.model_dump(mode="json") for item in evidence]
    return (
        "Extract Benzimidazoles ChemX records from the selected evidence only.\n"
        "Return JSON array only. Do not wrap it in Markdown.\n"
        "Schema fields: compound_id, smiles, target_type, target_relation, target_value, "
        "target_units, bacteria, evidence_id.\n"
        "Allowed target_type: MIC, pMIC, NOT_DETECTED. Allowed target_relation: =, <, >, NOT_DETECTED.\n"
        "Extract every MIC/pMIC mention for benzimidazole antibiotics against Staphylococcus aureus "
        "and Escherichia coli. Use one object per measurement. Do not deduplicate.\n"
        "Use NOT_DETECTED if a field is absent. Preserve ranges if present.\n"
        "Do not invent SMILES. If structure is not explicitly source-backed, set smiles to NOT_DETECTED.\n"
        "Every record must include the evidence_id of the evidence item supporting it.\n\n"
        f"Evidence JSON:\n{json.dumps(evidence_payload, ensure_ascii=False, indent=2)}"
    )


def _call_openai_compatible_model(config: LLMExtractionConfig, prompt: str) -> str:
    api_type = (config.api_type or "chat").lower()
    if api_type == "anthropic_messages":
        return _call_anthropic_messages_model(config, prompt)

    client = _openai_client(config)
    if api_type == "responses":
        response = client.responses.create(
            model=str(config.model),
            instructions="You extract source-backed chemical assay records as JSON only.",
            input=prompt,
            temperature=0,
            max_output_tokens=config.max_output_tokens,
        )
        return _response_text(response)

    response = client.chat.completions.create(
        model=str(config.model),
        messages=[
            {"role": "system", "content": "You extract source-backed chemical assay records as JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )
    content = response.choices[0].message.content
    return content or "[]"


def _openai_client(config: LLMExtractionConfig) -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("OpenAI-compatible client is not installed in the repository environment.") from exc

    kwargs: dict[str, Any] = {"api_key": config.api_key}
    if config.base_url:
        kwargs["base_url"] = config.base_url
    return OpenAI(**kwargs)


def _call_anthropic_messages_model(config: LLMExtractionConfig, prompt: str) -> str:
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError(
            "Anthropic SDK is not installed in the repository environment. "
            "Install it manually with: .\\.venv\\Scripts\\python.exe -m pip install anthropic"
        ) from exc

    kwargs: dict[str, Any] = {"api_key": config.api_key}
    if config.base_url:
        kwargs["base_url"] = _anthropic_sdk_base_url(config.base_url)
    client = anthropic.Anthropic(**kwargs)
    message = client.messages.create(
        model=str(config.model),
        max_tokens=config.max_output_tokens or 4096,
        temperature=0,
        system="You extract source-backed chemical assay records as JSON only.",
        messages=[{"role": "user", "content": prompt}],
    )
    return _anthropic_message_text(message)


def _response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return str(output_text)
    if hasattr(response, "model_dump"):
        data = response.model_dump()
        pieces: list[str] = []
        for item in data.get("output", []) or []:
            for content in item.get("content", []) or []:
                text = content.get("text")
                if text:
                    pieces.append(str(text))
        if pieces:
            return "\n".join(pieces)
    return "[]"


def _anthropic_message_text(message: Any) -> str:
    pieces: list[str] = []
    for block in getattr(message, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            pieces.append(str(text))
        elif isinstance(block, dict) and block.get("text"):
            pieces.append(str(block["text"]))
    return "\n".join(pieces) if pieces else "[]"


def _provider_error_message(config: LLMExtractionConfig, exc: Exception) -> str:
    api_type = (config.api_type or "chat").lower()
    if api_type == "responses":
        route = "/responses"
    elif api_type == "anthropic_messages":
        route = "/v1/messages"
    else:
        route = "/chat/completions"
    base_url = config.base_url.rstrip("/") if config.base_url else "OpenAI default"
    if api_type == "anthropic_messages" and config.base_url:
        base_url = _anthropic_sdk_base_url(config.base_url).rstrip("/")
    endpoint = base_url + route
    status_code = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    body = None
    if response is not None:
        try:
            body = response.text
        except Exception:  # noqa: BLE001
            body = None
    details = f"LLM provider call failed for endpoint {endpoint}, model={config.model!r}"
    if status_code:
        details += f", status={status_code}"
    if body:
        details += f", response={body[:500]}"
    else:
        details += f", error={exc}"
    if body and "no channel available for model" in body:
        details += ". The endpoint exists, but this model is not available on the configured API type; choose a model/channel pair exposed by the provider."
    elif status_code == 404:
        details += f". This usually means the configured base URL is not an OpenAI-compatible {route} endpoint."
    return details


def _optional_int(value: str | None) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _anthropic_sdk_base_url(base_url: str) -> str:
    """Anthropic SDK appends /v1/messages itself.

    OpenModel documents the API root as ``https://api.openmodel.ai/v1`` in some
    examples, but the current Anthropic Python SDK posts to ``/v1/messages``.
    Passing a base URL that already ends in ``/v1`` would therefore produce
    ``/v1/v1/messages``.
    """
    stripped = base_url.rstrip("/")
    return stripped[:-3] if stripped.endswith("/v1") else stripped


def _load_project_dotenv() -> None:
    project_root = Path(__file__).resolve().parents[3]
    dotenv_path = project_root / ".env"
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
