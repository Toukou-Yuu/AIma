"""llm.config 覆盖缺口测试。

覆盖：_resolve_env_value, _is_missing_api_key, MatchEndCondition.is_match_end,
_parse_profile 验证分支, _deep_merge, _get_required。"""

from __future__ import annotations

import pytest

from llm.config import (
    MatchEndCondition,
    _deep_merge,
    _get_required,
    _is_missing_api_key,
    _parse_profile,
    _resolve_env_value,
)


# --- _resolve_env_value ---

class TestResolveEnvValue:
    def test_literal_value(self) -> None:
        assert _resolve_env_value("sk-abc123") == "sk-abc123"

    def test_env_var(self, monkeypatch) -> None:
        monkeypatch.setenv("MY_API_KEY", "secret-value")
        assert _resolve_env_value("${MY_API_KEY}") == "secret-value"

    def test_env_var_missing(self, monkeypatch) -> None:
        monkeypatch.delenv("MISSING_KEY", raising=False)
        assert _resolve_env_value("${MISSING_KEY}") == ""

    def test_env_var_with_whitespace(self) -> None:
        result = _resolve_env_value("  ${SOME_VAR}  ")
        # stripped before match, so it should match
        # but if the var doesn't exist, returns ""
        assert isinstance(result, str)

    def test_non_env_string(self) -> None:
        assert _resolve_env_value("plain-string") == "plain-string"

    def test_dollar_brace_not_matching(self) -> None:
        # ${} with empty name doesn't match pattern (requires [A-Za-z_])
        assert _resolve_env_value("${}") == "${}"


# --- _is_missing_api_key ---

class TestIsMissingApiKey:
    def test_empty(self) -> None:
        assert _is_missing_api_key("") is True

    def test_placeholder_here(self) -> None:
        assert _is_missing_api_key("your-api-key-here") is True

    def test_placeholder_short(self) -> None:
        assert _is_missing_api_key("your-api-key") is True

    def test_valid_key(self) -> None:
        assert _is_missing_api_key("sk-abc123") is False

    def test_whitespace_only(self) -> None:
        assert _is_missing_api_key("   ") is True

    def test_placeholder_with_spaces(self) -> None:
        assert _is_missing_api_key("  your-api-key-here  ") is True


# --- MatchEndCondition.is_match_end ---

class TestMatchEndCondition:
    def test_hands_completed(self) -> None:
        mec = MatchEndCondition(type="hands", value=4, allow_negative=False)
        is_end, reason = mec.is_match_end(4, (25000, 25000, 25000, 25000))
        assert is_end
        assert "hands_completed" in reason

    def test_hands_not_completed(self) -> None:
        mec = MatchEndCondition(type="hands", value=8, allow_negative=False)
        is_end, reason = mec.is_match_end(4, (25000, 25000, 25000, 25000))
        assert not is_end
        assert reason == ""

    def test_negative_score_not_allowed(self) -> None:
        mec = MatchEndCondition(type="hands", value=8, allow_negative=False)
        is_end, reason = mec.is_match_end(2, (25000, -1000, 25000, 25000))
        assert is_end
        assert "negative_score" in reason
        assert "seat1" in reason

    def test_negative_score_allowed(self) -> None:
        mec = MatchEndCondition(type="hands", value=8, allow_negative=True)
        is_end, reason = mec.is_match_end(2, (25000, -1000, 25000, 25000))
        assert not is_end

    def test_multiple_negative_scores(self) -> None:
        mec = MatchEndCondition(type="hands", value=8, allow_negative=False)
        # first negative seat found
        is_end, reason = mec.is_match_end(1, (-1000, -2000, 30000, 25000))
        assert is_end
        assert "seat0" in reason


# --- _deep_merge ---

class TestDeepMerge:
    def test_simple_override(self) -> None:
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self) -> None:
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        override = {"a": {"y": 10, "z": 20}}
        result = _deep_merge(base, override)
        assert result == {"a": {"x": 1, "y": 10, "z": 20}, "b": 3}

    def test_override_replaces_non_dict(self) -> None:
        base = {"a": 1}
        override = {"a": {"nested": True}}
        result = _deep_merge(base, override)
        assert result == {"a": {"nested": True}}

    def test_empty_override(self) -> None:
        base = {"a": 1}
        result = _deep_merge(base, {})
        assert result == {"a": 1}

    def test_empty_base(self) -> None:
        override = {"a": 1}
        result = _deep_merge({}, override)
        assert result == {"a": 1}


# --- _get_required ---

class TestGetRequired:
    def test_simple_path(self) -> None:
        config = {"llm": {"model": "gpt-4"}}
        assert _get_required(config, "llm.model") == "gpt-4"

    def test_missing_key_raises(self) -> None:
        config = {"llm": {}}
        with pytest.raises(ValueError, match="缺少必需配置项"):
            _get_required(config, "llm.model")

    def test_missing_intermediate_raises(self) -> None:
        config = {}
        with pytest.raises(ValueError, match="缺少必需配置项"):
            _get_required(config, "llm.model")

    def test_non_dict_intermediate_raises(self) -> None:
        config = {"llm": "not-a-dict"}
        with pytest.raises(ValueError, match="缺少必需配置项"):
            _get_required(config, "llm.model")

    def test_single_key(self) -> None:
        config = {"seed": 42}
        assert _get_required(config, "seed") == 42


# --- _parse_profile ---

class TestParseProfile:
    def test_valid_profile(self) -> None:
        data = {
            "provider": "openai",
            "base_url": "https://api.openai.com",
            "api_key": "sk-test",
            "model": "gpt-4",
            "timeout_sec": 30.0,
            "max_context": 8000,
            "max_tokens": 1000,
        }
        profile = _parse_profile("test", data)
        assert profile.name == "test"
        assert profile.provider == "openai"
        assert profile.api_key == "sk-test"

    def test_invalid_provider(self) -> None:
        data = {
            "provider": "invalid",
            "base_url": "https://api.example.com",
            "api_key": "key",
            "model": "model",
            "timeout_sec": 30.0,
            "max_context": 8000,
            "max_tokens": 1000,
        }
        with pytest.raises(ValueError, match="must be one of"):
            _parse_profile("test", data)

    def test_not_dict_raises(self) -> None:
        with pytest.raises(ValueError, match="必须是对象"):
            _parse_profile("test", "not-a-dict")

    def test_max_context_zero_raises(self) -> None:
        data = {
            "provider": "openai",
            "base_url": "https://api.example.com",
            "api_key": "key",
            "model": "model",
            "timeout_sec": 30.0,
            "max_context": 0,
            "max_tokens": 100,
        }
        with pytest.raises(ValueError, match="positive"):
            _parse_profile("test", data)

    def test_max_tokens_zero_raises(self) -> None:
        data = {
            "provider": "openai",
            "base_url": "https://api.example.com",
            "api_key": "key",
            "model": "model",
            "timeout_sec": 30.0,
            "max_context": 8000,
            "max_tokens": 0,
        }
        with pytest.raises(ValueError, match="positive"):
            _parse_profile("test", data)

    def test_max_tokens_ge_max_context_raises(self) -> None:
        data = {
            "provider": "openai",
            "base_url": "https://api.example.com",
            "api_key": "key",
            "model": "model",
            "timeout_sec": 30.0,
            "max_context": 1000,
            "max_tokens": 1000,
        }
        with pytest.raises(ValueError, match="smaller than max_context"):
            _parse_profile("test", data)

    def test_env_var_in_api_key(self, monkeypatch) -> None:
        monkeypatch.setenv("TEST_API_KEY", "resolved-key")
        data = {
            "provider": "openai",
            "base_url": "https://api.example.com",
            "api_key": "${TEST_API_KEY}",
            "model": "model",
            "timeout_sec": 30.0,
            "max_context": 8000,
            "max_tokens": 1000,
        }
        profile = _parse_profile("test", data)
        assert profile.api_key == "resolved-key"
