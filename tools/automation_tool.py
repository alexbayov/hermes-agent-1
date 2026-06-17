"""Hermes browser automation recipe tool — self-registers on import."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.registry import registry
from agent.automation_tool_entry import (
    AUTOMATION_TOOL_DEFINITION,
    handle_run_browser_automation_recipe,
)

_TOOL_NAME = AUTOMATION_TOOL_DEFINITION["function"]["name"]
_SCHEMA = AUTOMATION_TOOL_DEFINITION["function"]

_REPO_ROOT = Path("/root/.hermes")


def _handler(args: dict[str, Any], **kw: Any) -> str:
    """Dispatch wrapper that pins repo_root for the automation runner."""
    return handle_run_browser_automation_recipe(args, repo_root=_REPO_ROOT)


registry.register(
    name=_TOOL_NAME,
    toolset="web_automation",
    schema=_SCHEMA,
    handler=_handler,
    emoji="🤖",
)
