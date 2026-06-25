from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class CommandToolConfig(BaseModel):
    name: str
    command: list[str] = Field(default_factory=list)
    output_format: str = "json_stdout"
    timeout_seconds: float = 300.0
    enabled: bool = True


def render_command(command: list[str], values: dict[str, str]) -> list[str]:
    return [part.format(**values) for part in command]


def run_command(command: list[str], timeout_seconds: float) -> subprocess.CompletedProcess[str]:
    if not command:
        raise ValueError("External tool command is empty")
    return subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
    )


def load_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def maybe_parse_json(text: str) -> Any | None:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return None
