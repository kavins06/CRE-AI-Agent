"""Input IDs bind a readable deal/record identity to exact Decimal input contents."""

import json
from collections.abc import Mapping
from hashlib import sha256


def input_id(prefix: str, values: Mapping[str, object]) -> str:
    content = json.dumps(dict(values), sort_keys=True, separators=(",", ":"), default=str)
    return f"{prefix}:{sha256(content.encode()).hexdigest()}"
