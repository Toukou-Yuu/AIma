"""Experiment schema validation tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from agents.schema import AgentSpec, ContextSpec, MemorySpec
from context.schema import ContextSpec as ContextSpecModule
from experiments.schema import (
    ArtifactSpec,
    ExperimentMetaSpec,
    ExperimentSpec,
    MatchSpec,
    RuleSpec,
    RuntimeSpec,
    SeedSpec,
)
from memory.schema import MemorySpec as MemorySpecModule
from models.schema import ModelSpec
from policies.schema import PolicySpec
from prompts.schema import PromptBudgetSpec, PromptSectionSpec, PromptSpec


class TestExperimentMetaSpec:
    def test_minimal(self) -> None:
        spec = ExperimentMetaSpec(id="test")
        assert spec.id == "test"
        assert spec.description == ""
        assert spec.tags == []

    def test_all_fields(self) -> None:
        spec = ExperimentMetaSpec(
            id="test",
            description="Test experiment",
            tags=["smoke", "v4"],
        )
        assert spec.id == "test"
        assert spec.description == "Test experiment"
        assert spec.tags == ["smoke", "v4"]

    def test_missing_id(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ExperimentMetaSpec()
        assert "id" in str(exc_info.value)


class TestRuleSpec:
    def test_minimal(self) -> None:
        spec = RuleSpec(version="v3.1.3")
        assert spec.version == "v3.1.3"
        assert spec.scope_file == "RULE_SCOPE.md"

    def test_custom_scope_file(self) -> None:
        spec = RuleSpec(version="v3.1.3", scope_file="custom_scope.md")
        assert spec.scope_file == "custom_scope.md"

    def test_missing_version(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            RuleSpec()
        assert "version" in str(exc_info.value)


class TestSeedSpec:
    def test_all_defaults(self) -> None:
        spec = SeedSpec()
        assert spec.start == 0
        assert spec.count == 1
        assert spec.explicit is None
        assert spec.common_walls is True

    def test_explicit_seeds(self) -> None:
        spec = SeedSpec(explicit=[1, 2, 3])
        assert spec.explicit == [1, 2, 3]

    def test_custom_count(self) -> None:
        spec = SeedSpec(count=10)
        assert spec.count == 10


class TestMatchSpec:
    def test_valid_presets(self) -> None:
        for preset in ["tonpuu", "hanchan", "custom"]:
            spec = MatchSpec(preset=preset)
            assert spec.preset == preset

    def test_invalid_preset(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            MatchSpec(preset="invalid_preset")
        errors = exc_info.value.errors()
        assert any("preset" in str(e) for e in errors)

    def test_defaults(self) -> None:
        spec = MatchSpec()
        assert spec.preset == "hanchan"
        assert spec.max_hands == 8
        assert spec.allow_negative is False
        assert spec.step_limit == 20000


class TestRuntimeSpec:
    def test_mode_enum(self) -> None:
        spec = RuntimeSpec(mode="serial")
        assert spec.mode == "serial"

    def test_defaults(self) -> None:
        spec = RuntimeSpec()
        assert spec.mode == "serial"
        assert spec.debug_snapshots is False
        assert spec.no_persist is True
        assert spec.resume is True
        assert spec.fail_fast is False


class TestArtifactSpec:
    def test_defaults(self) -> None:
        spec = ArtifactSpec()
        assert spec.output_root == "runs"
        assert spec.save_replay is True
        assert spec.save_events is True
        assert spec.save_decisions is True
        assert spec.save_prompts is False
        assert spec.sqlite_index is True


class TestModelSpec:
    def test_backend_enum(self) -> None:
        for backend in [
            "openai_compatible",
            "llama_cpp",
            "vllm_native",
            "mock",
            "replay",
            "dummy",
        ]:
            spec = ModelSpec(backend=backend)
            assert spec.backend == backend

    def test_invalid_backend(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ModelSpec(backend="invalid_backend")
        errors = exc_info.value.errors()
        assert any("backend" in str(e) for e in errors)

    def test_defaults(self) -> None:
        spec = ModelSpec(backend="dummy")
        assert spec.model_name == "dummy"
        assert spec.temperature == 0.0
        assert spec.max_tokens == 512


class TestPromptSectionSpec:
    def test_minimal(self) -> None:
        spec = PromptSectionSpec(id="test_section")
        assert spec.id == "test_section"
        assert spec.enabled is True

    def test_defaults(self) -> None:
        spec = PromptSectionSpec(id="test")
        assert spec.enabled is True
        assert spec.variant is None
        assert spec.options == {}

    def test_missing_id(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            PromptSectionSpec()
        assert "id" in str(exc_info.value)


class TestPromptBudgetSpec:
    def test_defaults(self) -> None:
        spec = PromptBudgetSpec()
        assert spec.truncation_policy == "drop_oldest_public_events"
        assert spec.max_prompt_tokens is None


class TestPromptSpec:
    def test_required_fields(self) -> None:
        spec = PromptSpec(
            template_id="test_template",
            version="v1",
            sections=[PromptSectionSpec(id="obs")],
        )
        assert spec.template_id == "test_template"
        assert spec.version == "v1"
        assert len(spec.sections) == 1

    def test_output_format_enum(self) -> None:
        for format in ["json_action", "natural_action"]:
            spec = PromptSpec(
                template_id="test",
                version="v1",
                sections=[],
                output_format=format,
            )
            assert spec.output_format == format

    def test_missing_template_id(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            PromptSpec(version="v1", sections=[])
        assert "template_id" in str(exc_info.value)


class TestContextSpec:
    def test_scope_enum(self) -> None:
        for scope in ["stateless", "per_turn", "per_hand", "per_match"]:
            spec = ContextSpecModule(scope=scope)
            assert spec.scope == scope

    def test_compression_enum(self) -> None:
        for compression in ["none", "snip", "collapse", "autocompact"]:
            spec = ContextSpecModule(compression=compression)
            assert spec.compression == compression

    def test_defaults(self) -> None:
        spec = ContextSpecModule()
        assert spec.scope == "stateless"
        assert spec.compression == "none"
        assert spec.include_public_events is True


class TestMemorySpec:
    def test_mode_enum(self) -> None:
        for mode in ["off", "passive"]:
            spec = MemorySpecModule(mode=mode)
            assert spec.mode == mode

    def test_layers_enum_values(self) -> None:
        spec = MemorySpecModule(layers=["hand", "match", "opponent"])
        assert spec.layers == ["hand", "match", "opponent"]

    def test_defaults(self) -> None:
        spec = MemorySpecModule()
        assert spec.mode == "off"
        assert spec.layers == []
        assert spec.store == "in_memory"
        assert spec.persist is False


class TestAgentSpec:
    def test_required_fields(self) -> None:
        spec = AgentSpec(
            prompt=PromptSpec(
                template_id="test",
                version="v1",
                sections=[PromptSectionSpec(id="obs")],
            ),
            model=ModelSpec(backend="dummy"),
        )
        assert spec.prompt.template_id == "test"
        assert spec.model.backend == "dummy"

    def test_defaults(self) -> None:
        spec = AgentSpec(
            prompt=PromptSpec(template_id="test", version="v1", sections=[]),
            model=ModelSpec(backend="dummy"),
        )
        assert spec.pipeline_id == "llm_fixed_v1"
        assert spec.parser == "strict_json"
        assert spec.fallback == "first_legal"

    def test_missing_prompt(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            AgentSpec(model=ModelSpec(backend="dummy"))
        assert "prompt" in str(exc_info.value)

    def test_missing_model(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            AgentSpec(
                prompt=PromptSpec(template_id="test", version="v1", sections=[])
            )
        assert "model" in str(exc_info.value)


class TestPolicySpec:
    def test_first_legal(self) -> None:
        spec = PolicySpec(type="first_legal", id="p0")
        assert spec.type == "first_legal"
        assert spec.id == "p0"
        assert spec.agent is None

    def test_random(self) -> None:
        spec = PolicySpec(type="random", id="p1")
        assert spec.type == "random"

    def test_fixed_heuristic(self) -> None:
        spec = PolicySpec(type="fixed_heuristic", id="p2")
        assert spec.type == "fixed_heuristic"

    def test_llm_with_agent(self) -> None:
        spec = PolicySpec(
            type="llm",
            id="llm0",
            agent=AgentSpec(
                prompt=PromptSpec(
                    template_id="test",
                    version="v1",
                    sections=[PromptSectionSpec(id="obs")],
                ),
                model=ModelSpec(backend="dummy"),
            ),
        )
        assert spec.type == "llm"
        assert spec.agent is not None
        assert spec.agent.model.backend == "dummy"

    def test_invalid_type(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            PolicySpec(type="invalid_type", id="p0")
        errors = exc_info.value.errors()
        assert any("type" in str(e) for e in errors)

    def test_missing_id(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            PolicySpec(type="first_legal")
        assert "id" in str(exc_info.value)


class TestExperimentSpec:
    def test_load_smoke_yaml(self) -> None:
        smoke_path = Path("AIma_v4_refactor_plan/examples/smoke.yaml")
        if not smoke_path.exists():
            pytest.skip("smoke.yaml not found")
        spec = ExperimentSpec.from_yaml(smoke_path)
        assert spec.experiment.id == "smoke"
        assert spec.match.preset == "hanchan"
        assert len(spec.policies) == 4
        assert "seat0" in spec.policies
        assert spec.policies["seat0"].type == "first_legal"

    def test_from_yaml_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            ExperimentSpec.from_yaml("nonexistent.yaml")

    def test_from_yaml_invalid_yaml(self, tmp_path: Path) -> None:
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("invalid: [yaml: content")
        # yaml.safe_load may parse this oddly; test real syntax error
        bad_yaml2 = tmp_path / "bad2.yaml"
        bad_yaml2.write_text("{\ninvalid json\n}")
        with pytest.raises(Exception):  # yaml.YAMLError or similar
            ExperimentSpec.from_yaml(bad_yaml2)

    def test_missing_required_field(self, tmp_path: Path) -> None:
        yaml_content = """
experiment:
  id: test
rules:
  version: v3.1.3
seeds:
  start: 0
  count: 1
match:
  preset: hanchan
# missing policies
"""
        yaml_file = tmp_path / "missing_policies.yaml"
        yaml_file.write_text(yaml_content)
        with pytest.raises(ValidationError) as exc_info:
            ExperimentSpec.from_yaml(yaml_file)
        assert "policies" in str(exc_info.value)

    def test_invalid_preset_in_yaml(self, tmp_path: Path) -> None:
        yaml_content = """
experiment:
  id: test
rules:
  version: v3.1.3
seeds:
  start: 0
  count: 1
match:
  preset: invalid_preset
policies:
  seat0:
    type: first_legal
    id: p0
"""
        yaml_file = tmp_path / "invalid_preset.yaml"
        yaml_file.write_text(yaml_content)
        with pytest.raises(ValidationError):
            ExperimentSpec.from_yaml(yaml_file)

    def test_nested_validation_error_path(self, tmp_path: Path) -> None:
        yaml_content = """
experiment:
  id: test
rules:
  version: v3.1.3
seeds:
  start: 0
  count: 1
match:
  preset: hanchan
policies:
  seat0:
    type: invalid_type
    id: p0
"""
        yaml_file = tmp_path / "nested_error.yaml"
        yaml_file.write_text(yaml_content)
        with pytest.raises(ValidationError) as exc_info:
            ExperimentSpec.from_yaml(yaml_file)
        # Error should reference nested path
        errors = exc_info.value.errors()
        assert any("policies" in str(e) or "seat0" in str(e) for e in errors)