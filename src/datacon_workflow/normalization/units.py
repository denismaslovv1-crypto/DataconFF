from __future__ import annotations

import re

from datacon_workflow.domains.benzimidazoles import MISSING_VALUE


def normalize_unit(value: str) -> str:
    if value == MISSING_VALUE:
        return value
    compact = re.sub(r"\s+", "", value)
    compact = compact.replace("μ", "µ").replace("−", "-")
    aliases = {
        "ug/mL": "µg/mL",
        "ugmL-1": "µg/mL",
        "µgmL-1": "µg/mL",
        "µg/mL": "µg/mL",
        "mcg/mL": "µg/mL",
        "microg/mL": "µg/mL",
        "mg/L": "µg/mL",
        "mgL-1": "µg/mL",
        "µM": "µM",
        "uM": "µM",
        "µmol/mL": "µmol/mL",
        "µmolmL-1": "µmol/mL",
        "umol/mL": "µmol/mL",
        "umolmL-1": "µmol/mL",
        "mmol/l": "mmol/L",
    }
    return aliases.get(compact, compact)
