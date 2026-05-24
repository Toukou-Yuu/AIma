"""Prompt template loader.

Loads prompt templates from YAML files and parses them into PromptSpec objects.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from prompts.schema import PromptBudgetSpec, PromptSectionSpec, PromptSpec

if TYPE_CHECKING:
    from typing import Any


logger = logging.getLogger(__name__)

# Default templates directory
DEFAULT_TEMPLATES_DIR = Path(__file__).parent / "templates"

# Template cache
_template_cache: dict[str, PromptSpec] = {}


class TemplateLoadError(Exception):
    """Error loading a prompt template."""

    pass


def load_template(
    template_id: str,
    templates_dir: Path | None = None,
    use_cache: bool = True,
) -> PromptSpec:
    """Load a prompt template by ID.

    Args:
        template_id: Template identifier (e.g., "riichi_json_action_v1")
        templates_dir: Directory containing templates (defaults to built-in)
        use_cache: Whether to use cached templates

    Returns:
        PromptSpec object

    Raises:
        TemplateLoadError: If template not found or invalid
    """
    # Check cache
    if use_cache and template_id in _template_cache:
        return _template_cache[template_id]

    # Find template file
    dir_path = templates_dir or DEFAULT_TEMPLATES_DIR
    template_file = dir_path / f"{template_id}.yaml"

    if not template_file.exists():
        raise TemplateLoadError(f"Template not found: {template_id}")

    # Load YAML
    try:
        with template_file.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise TemplateLoadError(f"Invalid YAML in template {template_id}: {e}") from e

    # Parse into PromptSpec
    try:
        spec = _parse_template(data)
    except (KeyError, TypeError, ValueError) as e:
        raise TemplateLoadError(f"Invalid template structure in {template_id}: {e}") from e

    # Validate template_id matches
    if spec.template_id != template_id:
        logger.warning(
            f"Template file {template_id}.yaml has template_id '{spec.template_id}'"
        )

    # Cache and return
    if use_cache:
        _template_cache[template_id] = spec

    return spec


def _parse_template(data: dict[str, Any]) -> PromptSpec:
    """Parse template data into PromptSpec.

    Args:
        data: Raw template data from YAML

    Returns:
        PromptSpec object
    """
    # Parse budget
    budget_data = data.get("budget", {})
    budget = PromptBudgetSpec(
        max_prompt_tokens=budget_data.get("max_prompt_tokens"),
        truncation_policy=budget_data.get("truncation_policy", "drop_oldest_public_events"),
    )

    # Parse sections
    sections: list[PromptSectionSpec] = []
    for section_data in data.get("sections", []):
        section = PromptSectionSpec(
            id=section_data["id"],
            enabled=section_data.get("enabled", True),
            variant=section_data.get("variant"),
            renderer=section_data.get("renderer"),
            source=section_data.get("source"),
            max_items=section_data.get("max_items"),
            max_tokens=section_data.get("max_tokens"),
            options=section_data.get("options", {}),
        )
        sections.append(section)

    return PromptSpec(
        template_id=data["template_id"],
        version=data.get("version", "1.0.0"),
        output_format=data.get("output_format", "json_action"),
        sections=sections,
        budget=budget,
    )


def clear_cache() -> None:
    """Clear the template cache."""
    _template_cache.clear()


def list_available_templates(templates_dir: Path | None = None) -> list[str]:
    """List available template IDs in a directory.

    Args:
        templates_dir: Directory to search (defaults to built-in)

    Returns:
        List of template IDs (without .yaml extension)
    """
    dir_path = templates_dir or DEFAULT_TEMPLATES_DIR
    if not dir_path.exists():
        return []

    return [f.stem for f in dir_path.glob("*.yaml")]


def reload_template(template_id: str, templates_dir: Path | None = None) -> PromptSpec:
    """Reload a template, bypassing cache.

    Args:
        template_id: Template identifier
        templates_dir: Directory containing templates

    Returns:
        PromptSpec object
    """
    return load_template(template_id, templates_dir=templates_dir, use_cache=False)