from __future__ import annotations

from datacon_workflow.domains.benzimidazoles import MISSING_VALUE


BACTERIA_ALIASES = {
    "S. aureus": "Staphylococcus aureus",
    "Staph. aureus": "Staphylococcus aureus",
    "Staphylococcus aureus": "Staphylococcus aureus",
    "E. coli": "Escherichia coli",
    "Escherichia coli": "Escherichia coli",
}


def normalize_bacteria(value: str) -> str:
    return BACTERIA_ALIASES.get(value.strip(), value.strip() if value != MISSING_VALUE else value)
