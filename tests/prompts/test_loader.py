"""测试 prompts/loader.py。

测试 template 加载。
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from prompts.loader import (
    TemplateLoadError,
    clear_cache,
    list_available_templates,
    load_template,
    reload_template,
)
from prompts.schema import PromptBudgetSpec, PromptSectionSpec, PromptSpec


class TestLoadTemplate:
    """load_template 测试。"""

    def test_loads_existing_template(self) -> None:
        """加载存在的模板。"""
        # 使用内置模板
        spec = load_template("riichi_json_action_v1", use_cache=False)

        assert spec.template_id == "riichi_json_action_v1"
        assert spec.version == "1.0.0"
        assert spec.output_format == "json_action"
        assert len(spec.sections) > 0

    def test_raises_error_for_nonexistent_template(self) -> None:
        """不存在模板抛出错误。"""
        with pytest.raises(TemplateLoadError) as exc_info:
            load_template("nonexistent_template", use_cache=False)

        assert "Template not found" in str(exc_info.value)

    def test_raises_error_for_invalid_yaml(self) -> None:
        """无效 YAML 抛出错误。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            templates_dir = Path(tmpdir)
            template_file = templates_dir / "invalid.yaml"
            template_file.write_text("invalid: yaml: content: :\n")

            with pytest.raises(TemplateLoadError) as exc_info:
                load_template("invalid", templates_dir=templates_dir, use_cache=False)

            assert "Invalid YAML" in str(exc_info.value)

    def test_raises_error_for_invalid_structure(self) -> None:
        """无效结构抛出错误。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            templates_dir = Path(tmpdir)
            template_file = templates_dir / "bad_structure.yaml"
            template_file.write_text(yaml.dump({"foo": "bar"}))  # 缺少 template_id

            with pytest.raises(TemplateLoadError) as exc_info:
                load_template("bad_structure", templates_dir=templates_dir, use_cache=False)

            assert "Invalid template structure" in str(exc_info.value)

    def test_caches_templates(self) -> None:
        """缓存模板。"""
        clear_cache()

        # 第一次加载
        spec1 = load_template("riichi_json_action_v1", use_cache=True)

        # 第二次加载（应该从缓存获取）
        spec2 = load_template("riichi_json_action_v1", use_cache=True)

        # 同一个对象
        assert spec1 is spec2

    def test_bypasses_cache(self) -> None:
        """跳过缓存。"""
        clear_cache()

        spec1 = load_template("riichi_json_action_v1", use_cache=True)
        spec2 = load_template("riichi_json_action_v1", use_cache=False)

        # 不是同一个对象（缓存被跳过）
        assert spec1 is not spec2

    def test_loads_from_custom_directory(self) -> None:
        """从自定义目录加载。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            templates_dir = Path(tmpdir)

            # 创建自定义模板
            custom_template = {
                "template_id": "custom_test",
                "version": "1.0.0",
                "output_format": "json_action",
                "budget": {
                    "max_prompt_tokens": 4000,
                },
                "sections": [
                    {
                        "id": "system_prompt",
                        "enabled": True,
                        "renderer": "system_prompt",
                    },
                ],
            }
            template_file = templates_dir / "custom_test.yaml"
            template_file.write_text(yaml.dump(custom_template))

            spec = load_template("custom_test", templates_dir=templates_dir, use_cache=False)

            assert spec.template_id == "custom_test"
            assert spec.budget.max_prompt_tokens == 4000


class TestParseTemplate:
    """模板解析测试。"""

    def test_parses_full_template(self) -> None:
        """解析完整模板。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            templates_dir = Path(tmpdir)

            template_data = {
                "template_id": "test_v1",
                "version": "2.0.0",
                "output_format": "natural_action",
                "budget": {
                    "max_prompt_tokens": 5000,
                    "truncation_policy": "drop_oldest",
                },
                "sections": [
                    {
                        "id": "section1",
                        "enabled": True,
                        "variant": "riichi",
                        "renderer": "system_prompt",
                        "source": "memory_db",
                        "max_items": 10,
                        "max_tokens": 200,
                        "options": {"key": "value"},
                    },
                    {
                        "id": "section2",
                        "enabled": False,
                    },
                ],
            }
            template_file = templates_dir / "test_v1.yaml"
            template_file.write_text(yaml.dump(template_data))

            spec = load_template("test_v1", templates_dir=templates_dir, use_cache=False)

            assert spec.template_id == "test_v1"
            assert spec.version == "2.0.0"
            assert spec.output_format == "natural_action"
            assert spec.budget.max_prompt_tokens == 5000
            assert spec.budget.truncation_policy == "drop_oldest"

            assert len(spec.sections) == 2
            s1 = spec.sections[0]
            assert s1.id == "section1"
            assert s1.enabled is True
            assert s1.variant == "riichi"
            assert s1.renderer == "system_prompt"
            assert s1.source == "memory_db"
            assert s1.max_items == 10
            assert s1.max_tokens == 200
            assert s1.options == {"key": "value"}

            s2 = spec.sections[1]
            assert s2.id == "section2"
            assert s2.enabled is False

    def test_uses_defaults_for_missing_fields(self) -> None:
        """缺失字段使用默认值。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            templates_dir = Path(tmpdir)

            template_data = {
                "template_id": "minimal",
                # 缺少 version, output_format, budget, sections
            }
            template_file = templates_dir / "minimal.yaml"
            template_file.write_text(yaml.dump(template_data))

            spec = load_template("minimal", templates_dir=templates_dir, use_cache=False)

            assert spec.template_id == "minimal"
            assert spec.version == "1.0.0"
            assert spec.output_format == "json_action"
            assert spec.budget.max_prompt_tokens is None
            assert spec.budget.truncation_policy == "drop_oldest_public_events"
            assert spec.sections == []


class TestClearCache:
    """clear_cache 测试。"""

    def test_clears_cache(self) -> None:
        """清空缓存。"""
        # 加载并缓存
        load_template("riichi_json_action_v1", use_cache=True)

        # 清空缓存
        clear_cache()

        # 再次加载，应该是新对象
        spec1 = load_template("riichi_json_action_v1", use_cache=True)
        load_template("riichi_json_action_v1", use_cache=True)  # 再次缓存
        clear_cache()
        spec2 = load_template("riichi_json_action_v1", use_cache=True)

        assert spec1 is not spec2


class TestListAvailableTemplates:
    """list_available_templates 测试。"""

    def test_lists_builtin_templates(self) -> None:
        """列出内置模板。"""
        templates = list_available_templates()

        assert "riichi_json_action_v1" in templates

    def test_lists_custom_templates(self) -> None:
        """列出自定义模板。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            templates_dir = Path(tmpdir)

            # 创建多个模板文件
            for name in ["a", "b", "c"]:
                template_file = templates_dir / f"{name}.yaml"
                template_file.write_text(yaml.dump({"template_id": name}))

            templates = list_available_templates(templates_dir=templates_dir)

            assert set(templates) == {"a", "b", "c"}

    def test_returns_empty_for_nonexistent_dir(self) -> None:
        """不存在目录返回空列表。"""
        templates = list_available_templates(templates_dir=Path("/nonexistent"))
        assert templates == []


class TestReloadTemplate:
    """reload_template 测试。"""

    def test_reloads_template(self) -> None:
        """重新加载模板。"""
        clear_cache()

        # 先缓存一个
        load_template("riichi_json_action_v1", use_cache=True)

        # reload
        spec = reload_template("riichi_json_action_v1")

        assert spec.template_id == "riichi_json_action_v1"

    def test_reloads_from_custom_dir(self) -> None:
        """从自定义目录重新加载。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            templates_dir = Path(tmpdir)

            template_file = templates_dir / "test.yaml"
            template_file.write_text(yaml.dump({"template_id": "test"}))

            spec = reload_template("test", templates_dir=templates_dir)

            assert spec.template_id == "test"


class TestTemplateStructure:
    """模板结构测试。"""

    def test_section_spec_defaults(self) -> None:
        """PromptSectionSpec 默认值。"""
        spec = PromptSectionSpec(id="test")

        assert spec.id == "test"
        assert spec.enabled is True
        assert spec.variant is None
        assert spec.renderer is None
        assert spec.source is None
        assert spec.max_items is None
        assert spec.max_tokens is None
        assert spec.options == {}

    def test_budget_spec_defaults(self) -> None:
        """PromptBudgetSpec 默认值。"""
        spec = PromptBudgetSpec()

        assert spec.max_prompt_tokens is None
        assert spec.truncation_policy == "drop_oldest_public_events"

    def test_prompt_spec_defaults(self) -> None:
        """PromptSpec 默认值。"""
        spec = PromptSpec(template_id="test", version="1.0", sections=[])

        assert spec.template_id == "test"
        assert spec.version == "1.0"
        assert spec.output_format == "json_action"
        assert spec.sections == []
        assert spec.budget.max_prompt_tokens is None