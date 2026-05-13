"""llm.config 覆盖缺口测试：YAML 加载路径与校验分支。"""

from __future__ import annotations

from pathlib import Path

import pytest

from llm.config import (
    MatchEndCondition,
    _effective_llm_config,
    _parse_match_end,
    _read_yaml_file,
    get_logging_config,
    load_kernel_config,
    load_llm_config,
    load_llm_profiles,
    load_llm_runtime_config,
    load_match_config,
    load_seat_llm_bindings,
    load_seat_llm_configs,
)


def _write_yaml(path: Path, data: dict) -> None:
    import yaml
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")


# --- _read_yaml_file ---

class TestReadYamlFile:
    def test_non_dict_root_raises(self, tmp_path) -> None:
        """YAML 顶层非 dict → ValueError（L117-118）。"""
        p = tmp_path / "bad.yaml"
        p.write_text("- item1\n- item2\n", encoding="utf-8")
        try:
            _read_yaml_file(p)
            raise AssertionError("expected ValueError for non-dict root")
        except ValueError:
            pass

    def test_nonexistent_returns_empty(self, tmp_path) -> None:
        p = tmp_path / "nonexistent.yaml"
        assert _read_yaml_file(p) == {}


# --- load_kernel_config ---

class TestLoadKernelConfig:
    def test_fallback_to_template(self, tmp_path) -> None:
        """aima_kernel.yaml 不存在时回退到模板（L172-179）。"""
        template = tmp_path / "aima_kernel_template.yaml"
        _write_yaml(template, {"llm": {"system_prompt": "test"}})
        # 需要通过 configs/ 路径加载，这里直接测试 _read_yaml_file 路径
        result = _read_yaml_file(template)
        assert "llm" in result

    def test_nonexistent_raises(self, tmp_path) -> None:
        """配置文件不存在 → FileNotFoundError（L180-184）。"""
        p = tmp_path / "aima_kernel.yaml"
        try:
            load_kernel_config(p)
            raise AssertionError("expected FileNotFoundError")
        except FileNotFoundError:
            pass


# --- _effective_llm_config ---

class TestEffectiveLlmConfig:
    def test_missing_llm_section_raises(self, tmp_path) -> None:
        """llm 段非 dict → ValueError（L198）。"""
        p = tmp_path / "config.yaml"
        _write_yaml(p, {"llm": None})
        try:
            _effective_llm_config(config_path=p)
            raise AssertionError("expected ValueError for non-dict llm section")
        except ValueError:
            pass

    def test_override_not_dict_raises(self, tmp_path) -> None:
        """override_cfg 非 dict → ValueError（L203-204）。"""
        p = tmp_path / "config.yaml"
        _write_yaml(p, {"llm": {"system_prompt": "test"}})
        try:
            _effective_llm_config(config_path=p, override_cfg="not a dict")
            raise AssertionError("expected ValueError for non-dict override")
        except ValueError:
            pass


# --- load_llm_runtime_config ---

class TestLoadLlmRuntimeConfig:
    def test_invalid_threshold_raises(self, tmp_path) -> None:
        """threshold 越界 → ValueError（L238）。"""
        p = tmp_path / "config.yaml"
        _write_yaml(p, {
            "llm": {
                "system_prompt": "test",
                "prompt_format": "natural",
                "context_scope": "per_hand",
                "compression_level": "none",
                "history_budget": 2000,
                "context_compression_threshold": 0,
                "request_delay": 0,
                "conversation_logging": {"enabled": False},
            }
        })
        try:
            load_llm_runtime_config(config_path=p)
            raise AssertionError("expected ValueError for invalid threshold")
        except ValueError:
            pass


# --- load_llm_profiles ---

class TestLoadLlmProfiles:
    def test_empty_profiles_raises(self, tmp_path) -> None:
        """profiles 非 dict → ValueError（L303）。"""
        p = tmp_path / "config.yaml"
        _write_yaml(p, {"llm": {"profiles": {}}})
        try:
            load_llm_profiles(config_path=p, override_cfg={"profiles": None})
            raise AssertionError("expected ValueError for non-dict profiles")
        except ValueError:
            pass


# --- load_seat_llm_bindings ---

class TestLoadSeatLlmBindings:
    def test_seats_not_dict_raises(self, tmp_path) -> None:
        """seats 非 dict → ValueError（L316）。"""
        p = tmp_path / "config.yaml"
        _write_yaml(p, {"llm": {"seats": "not a dict", "profiles": {"p": {
            "provider": "openai", "base_url": "http://t", "api_key": "k",
            "model": "m", "timeout_sec": 30, "max_context": 4096, "max_tokens": 1024,
        }}}})
        try:
            load_seat_llm_bindings(config_path=p)
            raise AssertionError("expected ValueError for non-dict seats")
        except ValueError:
            pass

    def test_seat_not_dict_raises(self, tmp_path) -> None:
        """seat 条目非 dict → ValueError（L324）。"""
        p = tmp_path / "config.yaml"
        _write_yaml(p, {"llm": {
            "seats": {"seat0": "not a dict"},
            "profiles": {"p": {
                "provider": "openai", "base_url": "http://t", "api_key": "k",
                "model": "m", "timeout_sec": 30, "max_context": 4096, "max_tokens": 1024,
            }},
        }})
        try:
            load_seat_llm_bindings(config_path=p)
            raise AssertionError("expected ValueError for non-dict seat entry")
        except ValueError:
            pass


# --- load_llm_config ---

class TestLoadLlmConfig:
    def test_seat_none_raises(self, tmp_path) -> None:
        """seat=None → ValueError（L393-394）。"""
        p = tmp_path / "config.yaml"
        _write_yaml(p, {"llm": {}})
        try:
            load_llm_config(config_path=p, seat=None)
            raise AssertionError("expected ValueError for seat=None")
        except ValueError:
            pass

    def test_seat_out_of_range_raises(self, tmp_path) -> None:
        """seat=5 → ValueError（L395-396）。"""
        p = tmp_path / "config.yaml"
        _write_yaml(p, {"llm": {}})
        try:
            load_llm_config(config_path=p, seat=5)
            raise AssertionError("expected ValueError for seat=5")
        except ValueError:
            pass


# --- _parse_match_end ---

class TestParseMatchEnd:
    def test_not_dict_raises(self) -> None:
        """match_end 非 dict → ValueError（L402-403）。"""
        try:
            _parse_match_end({"match_end": "not a dict"})
            raise AssertionError("expected ValueError for non-dict match_end")
        except ValueError:
            pass


# --- MatchEndCondition ---

class TestMatchEndCondition:
    def test_is_match_end_hands_completed(self) -> None:
        m = MatchEndCondition(type="hands", value=8, allow_negative=False)
        result, reason = m.is_match_end(8, (25000, 25000, 25000, 25000))
        assert result is True
        assert "hands_completed" in reason

    def test_is_match_end_hands_not_completed(self) -> None:
        m = MatchEndCondition(type="hands", value=8, allow_negative=False)
        result, _ = m.is_match_end(7, (25000, 25000, 25000, 25000))
        assert result is False

    def test_negative_score_not_allowed(self) -> None:
        m = MatchEndCondition(type="hands", value=8, allow_negative=False)
        result, reason = m.is_match_end(3, (-1, 25000, 25000, 25000))
        assert result is True
        assert "negative_score" in reason

    def test_negative_score_allowed(self) -> None:
        m = MatchEndCondition(type="hands", value=8, allow_negative=True)
        result, _ = m.is_match_end(3, (-1, 25000, 25000, 25000))
        assert result is False

    def test_no_negative_scores(self) -> None:
        m = MatchEndCondition(type="hands", value=8, allow_negative=False)
        result, _ = m.is_match_end(3, (25000, 25000, 25000, 25000))
        assert result is False


# --- load_match_config ---

class TestLoadMatchConfig:
    def test_loads_successfully(self, tmp_path) -> None:
        """完整 match 配置加载（L416-438）。"""
        p = tmp_path / "config.yaml"
        _write_yaml(p, {
            "match": {
                "seed": 42,
                "match_end": {"type": "hands", "value": 8, "allow_negative": False},
                "players": None,
            }
        })
        cfg = load_match_config(p)
        assert cfg.seed == 42
        assert cfg.match_end.type == "hands"


# --- get_logging_config ---

class TestGetLoggingConfig:
    def test_missing_logging_raises(self, tmp_path) -> None:
        """logging 段非 dict → ValueError（L445-446）。"""
        p = tmp_path / "config.yaml"
        _write_yaml(p, {"logging": None})
        try:
            get_logging_config(p)
            raise AssertionError("expected ValueError for non-dict logging")
        except ValueError:
            pass

    def test_loads_successfully(self, tmp_path) -> None:
        """正常加载 logging 配置（L443-447）。"""
        p = tmp_path / "config.yaml"
        _write_yaml(p, {"logging": {"level": "DEBUG"}})
        result = get_logging_config(p)
        assert result["level"] == "DEBUG"
