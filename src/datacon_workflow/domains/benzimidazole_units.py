from __future__ import annotations

import re

from datacon_workflow.domains.benzimidazoles import MISSING_VALUE


UNIT_TOKEN_RE = re.compile(
    r"""
    (?P<unit>
        [µμu]mol\s*/?\s*mL\s*(?:[-−]\s*1)?
        |[µμu]g\s*/?\s*mL\s*(?:[-−]\s*1)?
        |mg\s*/?\s*L\s*(?:[-−]\s*1)?
        |mM
        |[µμu]M
    )
    """,
    re.I | re.X,
)
MIC_HEADER_UNIT_RE = re.compile(
    r"""
    \(
        \s*MIC\s*
        [,;:]\s*
        (?P<unit>
            [µμu]mol\s*/?\s*mL\s*(?:[-−]\s*1)?
            |[µμu]g\s*/?\s*mL\s*(?:[-−]\s*1)?
            |mg\s*/?\s*L\s*(?:[-−]\s*1)?
            |mM
            |[µμu]M
        )
        \s*
    \)
    """,
    re.I | re.X,
)


def extract_target_unit_from_evidence(text: str, value: str | None = None) -> str:
    """Return an evidence-backed unit from the same assay chunk.

    The helper is intentionally conservative: it only looks inside the supplied
    evidence text, preferring units next to the matched numeric value and then
    MIC table/header units in that same chunk.
    """
    if not text:
        return MISSING_VALUE
    unit = _unit_near_value(text, value) if value else MISSING_VALUE
    if unit != MISSING_VALUE:
        return unit
    header = MIC_HEADER_UNIT_RE.search(text)
    if header:
        return _clean_unit(header.group("unit"))
    generic = UNIT_TOKEN_RE.search(text)
    return _clean_unit(generic.group("unit")) if generic else MISSING_VALUE


def _unit_near_value(text: str, value: str | None) -> str:
    if not value:
        return MISSING_VALUE
    values = [piece.strip() for piece in re.split(r"[-–]", value) if piece.strip()]
    if not values:
        return MISSING_VALUE
    escaped = "|".join(re.escape(piece) for piece in values)
    after = re.search(rf"(?<![\d.])(?:{escaped})(?![\d.])\s*(?P<context>.{{0,30}})", text, re.I)
    if after:
        unit = UNIT_TOKEN_RE.search(after.group("context"))
        if unit:
            return _clean_unit(unit.group("unit"))
    before = re.search(rf"(?P<context>.{{0,30}})(?<![\d.])(?:{escaped})(?![\d.])", text, re.I)
    if before:
        unit = UNIT_TOKEN_RE.search(before.group("context"))
        if unit:
            return _clean_unit(unit.group("unit"))
    return MISSING_VALUE


def _clean_unit(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())
