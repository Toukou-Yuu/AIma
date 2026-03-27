"""从模型原始文本中解析 JSON 动作。"""

from __future__ import annotations

import json
import re
from typing import Any


def extract_json_object(text: str) -> dict[str, Any]:
    """
    从模型输出中取单个 JSON 对象。

    容忍首尾空白、可选 ```json 围栏、行内前后杂质。
    """
    s = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", s, re.DOTALL)
    if fence:
        s = fence.group(1).strip()
    first = s.find("{")
    last = s.rfind("}")
    if first == -1 or last == -1 or last <= first:
        msg = f"no JSON object in model output: {text[:200]!r}..."
        raise ValueError(msg)
    chunk = s[first : last + 1]
    try:
        obj = json.loads(chunk)
    except json.JSONDecodeError as e:
        msg = f"invalid JSON: {chunk[:300]!r}"
        raise ValueError(msg) from e
    if not isinstance(obj, dict):
        msg = f"JSON root must be object, got {type(obj)}"
        raise TypeError(msg)
    return obj
