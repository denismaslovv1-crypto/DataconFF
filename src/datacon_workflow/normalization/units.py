from __future__ import annotations

import re

from datacon_workflow.domains.benzimidazoles import MISSING_VALUE


def normalize_unit(value: str) -> str:
    if value == MISSING_VALUE:
        return value
    compact = re.sub(r"\s+", "", value)
    aliases = {
        "ug/mL": "µg/mL",
        "μg/mL": "µg/mL",
        "mcg/mL": "µg/mL",
        "microg/mL": "µg/mL",
        "mg/L": "µg/mL",
        "mmol/l": "mmol/L",
    }
    return aliases.get(compact, compact)
