from __future__ import annotations

import re
from pathlib import Path

TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9_+\-./]*")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def tokenize(value: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_RE.finditer(value)]


def slugify(value: str) -> str:
    normalized = normalize_whitespace(value).lower()
    normalized = re.sub(r"[^a-zа-яё0-9]+", "-", normalized, flags=re.IGNORECASE)
    return normalized.strip("-") or "chunk"

