"""parse.py 错误分支覆盖。"""

from __future__ import annotations

import json
from unittest.mock import patch

from llm.parse import extract_json_object


def test_no_braces_raises_value_error() -> None:
    """无花括号的文本应抛 ValueError。"""
    try:
        extract_json_object("hello world, no json here")
    except ValueError as e:
        assert "no JSON object" in str(e)
    else:
        raise AssertionError("应抛出 ValueError")


def test_invalid_json_raises_value_error() -> None:
    """有花括号但内容非法 JSON 应抛 ValueError。"""
    try:
        extract_json_object("{invalid json content}")
    except ValueError as e:
        assert "invalid JSON" in str(e)
    else:
        raise AssertionError("应抛出 ValueError")


def test_json_array_root_raises_type_error() -> None:
    """JSON 根为数组（非 dict）时应抛 TypeError。

    注意：正常流程中此分支不可达（brace 提取保证 chunk 以 { 开头）。
    通过 mock json.loads 模拟返回 list 来覆盖该分支。
    """
    original = json.loads

    def _mock_loads(s, **kw):
        # 只对包含特定标记的 chunk 返回 list
        if s == '{"mock": true}':
            return [1, 2, 3]
        return original(s, **kw)

    with patch("llm.parse.json.loads", side_effect=_mock_loads):
        try:
            extract_json_object('{"mock": true}')
        except TypeError as e:
            assert "object" in str(e)
        else:
            raise AssertionError("应抛出 TypeError")


def test_extract_json_basic() -> None:
    """正常 JSON 提取成功。"""
    result = extract_json_object('{"kind": "draw", "seat": 0}')
    assert result == {"kind": "draw", "seat": 0}


def test_extract_json_with_surrounding_text() -> None:
    """前后有杂质文本时仍能提取。"""
    result = extract_json_object('thinking... {"kind": "discard", "tile": "3m"} done')
    assert result["kind"] == "discard"


def test_closing_before_opening() -> None:
    """} 出现在 { 之前，应抛 ValueError。"""
    try:
        extract_json_object("} abc {")
    except ValueError:
        pass
    else:
        raise AssertionError("应抛出 ValueError")


def test_extract_json_with_fence() -> None:
    """```json 围栏包裹应正常解析。"""
    text = '说明\n```json\n{"kind":"draw","seat":0}\n```\n'
    assert extract_json_object(text) == {"kind": "draw", "seat": 0}
