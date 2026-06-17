"""Tool schema and handler for Hermes browser automation recipes.

This module is intentionally independent from the concrete `model_tools`
registry implementation. The installed Hermes tool registry can import
`AUTOMATION_TOOL_DEFINITION` and dispatch `run_browser_automation_recipe` to
`handle_run_browser_automation_recipe`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from agent.automation_state import write_automation_task_state
from agent.automation_tool import (
    AutomationRunRequest,
    AutomationToolError,
    run_automation_recipe,
    summarize_automation_result,
)

TOOL_NAME = "run_browser_automation_recipe"

AUTOMATION_TOOL_DEFINITION: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": (
            "Run a Hermes browser automation YAML recipe through the isolated "
            "hermes-automation runner. Returns done/blocked JSON summary and "
            "writes task-state YAML. Do not use to bypass CAPTCHA, 2FA, phone, "
            "passkey, or anti-bot gates."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "recipe": {
                    "type": "string",
                    "description": "Path to a hermes-automation sites/*.yaml recipe.",
                },
                "task_id": {
                    "type": "string",
                    "description": "Stable task/checkpoint id for this automation run.",
                },
                "fields": {
                    "type": "object",
                    "description": "Recipe field values such as email/name/profile inputs. Secrets must come from approved sources and are redacted by the runner checkpoint.",
                    "additionalProperties": True,
                },
                "state_dir": {
                    "type": "string",
                    "description": "Automation checkpoint directory.",
                    "default": "state",
                },
                "artifacts_dir": {
                    "type": "string",
                    "description": "Automation screenshots/trace artifacts directory.",
                    "default": "artifacts",
                },
                "task_state_dir": {
                    "type": "string",
                    "description": "Hermes task-state YAML directory.",
                    "default": "profile/task-state",
                },
                "headless": {"type": "boolean", "default": True},
                "reset": {"type": "boolean", "default": False},
                "executable_path": {
                    "type": "string",
                    "description": "Optional Chrome/Chromium executable path.",
                },
            },
            "required": ["recipe", "task_id"],
            "additionalProperties": False,
        },
    },
}


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def handle_run_browser_automation_recipe(
    arguments: Mapping[str, Any] | str,
    *,
    repo_root: str | Path | None = None,
) -> str:
    """Execute the automation tool and return compact JSON text for a tool result."""

    if isinstance(arguments, str):
        try:
            args = json.loads(arguments or "{}")
        except json.JSONDecodeError as e:
            return json.dumps({"ok": False, "error": f"invalid JSON arguments: {e}"})
    else:
        args = dict(arguments)

    request = AutomationRunRequest(
        recipe=str(args.get("recipe") or ""),
        task_id=str(args.get("task_id") or ""),
        fields=_as_mapping(args.get("fields")),
        state_dir=str(args.get("state_dir") or "state"),
        artifacts_dir=str(args.get("artifacts_dir") or "artifacts"),
        headless=bool(args.get("headless", True)),
        reset=bool(args.get("reset", False)),
        executable_path=args.get("executable_path") or None,
        include_actions=False,
    )

    if not request.recipe or not request.task_id:
        return json.dumps({"ok": False, "error": "recipe and task_id are required"})

    try:
        result = run_automation_recipe(request, cwd=repo_root)
        task_state = write_automation_task_state(
            result.payload,
            task_state_dir=str(args.get("task_state_dir") or "profile/task-state"),
        )
    except AutomationToolError as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

    payload = {
        "ok": True,
        "status": result.status,
        "success": result.success,
        "blocked_reason": result.blocked_reason,
        "summary": summarize_automation_result(result),
        "task_state_path": str(task_state.path),
        "result": {
            "task_id": result.payload.get("task_id"),
            "site": result.payload.get("site"),
            "final_url": result.payload.get("final_url"),
            "completed_steps": result.payload.get("completed_steps") or [],
            "artifacts": result.payload.get("artifacts") or {},
            "blocker": result.payload.get("blocker"),
        },
    }
    return json.dumps(payload, ensure_ascii=False)
