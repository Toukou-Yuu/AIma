"""LLM profile 配置与按座位 client 构造测试。"""

from __future__ import annotations

from pathlib import Path


def _write_config(path: Path, *, api_key: str = "sk-test") -> None:
    path.write_text(
        "\n".join(
            [
                "llm:",
                "  prompt_format: natural",
                "  context_scope: per_hand",
                "  compression_level: collapse",
                "  history_budget: 10",
                "  context_compression_threshold: 0.95",
                "  request_delay: 0.5",
                "  conversation_logging:",
                "    enabled: false",
                "  system_prompt: 你是麻将牌手",
                "  profiles:",
                "    local:",
                "      provider: openai",
                "      base_url: http://localhost:8080/v1",
                f"      api_key: {api_key}",
                "      model: qwen-local",
                "      timeout_sec: 60",
                "      max_context: 8192",
                "      max_tokens: 512",
                "    cloud:",
                "      provider: openai",
                "      base_url: https://api.deepseek.com/v1",
                "      api_key: ${AIMA_TEST_API_KEY}",
                "      model: deepseek-chat",
                "      timeout_sec: 120",
                "      max_context: 64000",
                "      max_tokens: 1024",
                "  seats:",
                "    seat0:",
                "      profile: local",
                "    seat1:",
                "      profile: cloud",
                "    seat2:",
                "      profile: local",
                "    seat3:",
                "      profile: cloud",
                "match:",
                "  seed: 42",
                "  match_end:",
                "    type: hands",
                "    value: 1",
                "    allow_negative: false",
            ]
        ),
        encoding="utf-8",
    )


def test_load_seat_llm_configs_binds_profiles(tmp_path: Path, monkeypatch) -> None:
    from llm.config import load_seat_llm_configs

    monkeypatch.setenv("AIMA_TEST_API_KEY", "sk-env")
    config_path = tmp_path / "kernel.yaml"
    _write_config(config_path)

    configs = load_seat_llm_configs(config_path=config_path)

    assert configs[0] is not None
    assert configs[0].base_url == "http://localhost:8080/v1"
    assert configs[0].model == "qwen-local"
    assert configs[0].max_context == 8192
    assert configs[1] is not None
    assert configs[1].api_key == "sk-env"
    assert configs[1].max_context == 64000
    assert configs[2] is not None
    assert configs[2].model == "qwen-local"


def test_load_seat_llm_configs_rejects_missing_profile(tmp_path: Path) -> None:
    import pytest

    from llm.config import load_seat_llm_configs

    config_path = tmp_path / "kernel.yaml"
    _write_config(config_path)
    text = config_path.read_text(encoding="utf-8")
    config_path.write_text(text.replace("profile: cloud", "profile: missing", 1), encoding="utf-8")

    with pytest.raises(ValueError, match="不存在的 profile"):
        load_seat_llm_configs(config_path=config_path)


def test_load_seat_llm_configs_preserves_placeholder_profile_budget(tmp_path: Path) -> None:
    from llm.config import load_seat_llm_configs

    config_path = tmp_path / "kernel.yaml"
    _write_config(config_path, api_key="your-api-key-here")

    configs = load_seat_llm_configs(config_path=config_path)

    assert configs[0].has_api_key is False
    assert configs[0].max_context == 8192
    assert configs[2].has_api_key is False


def test_build_seat_clients_rejects_missing_client_config(tmp_path: Path) -> None:
    import pytest

    from llm.config import load_seat_llm_configs
    from llm.protocol import build_seat_clients

    config_path = tmp_path / "kernel.yaml"
    _write_config(config_path, api_key="your-api-key-here")

    configs = load_seat_llm_configs(config_path=config_path)

    with pytest.raises(ValueError, match="seat0"):
        build_seat_clients(configs)
