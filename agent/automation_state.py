"""Task-state helpers for Hermes automation results."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml


@dataclass(frozen=True)
class AutomationTaskStateUpdate:
    """Result of writing an automation task-state file."""

    path: Path
    state: Mapping[str, Any]


def state_from_automation_payload(
    payload: Mapping[str, Any],
    *,
    task_title: str | None = None,
    current_goal: str | None = None,
) -> dict[str, Any]:
    """Convert `hermes.automation.result.v1` payload to task-state protocol."""

    task_id = str(payload.get("task_id") or "automation-task")
    status = "done" if payload.get("success") else "blocked"
    blocked_reason = payload.get("blocked_reason") or payload.get("error")
    completed_steps = list(payload.get("completed_steps") or [])
    last_safe_step = completed_steps[-1] if completed_steps else None

    next_step = None
    requires_approval = False
    if status == "blocked":
        requires_approval = True
        reason = str(blocked_reason or "automation_blocked")
        if reason == "email_verification_required":
            next_step = "Complete or fetch email verification, then resume from checkpoint."
        elif reason in {
            "captcha_visible",
            "two_factor_required",
            "phone_verification_required",
            "passkey_required",
        }:
            next_step = "Ask the user to complete the security gate, then resume from checkpoint."
        else:
            next_step = "Inspect blocker/error and choose an approved recovery step."

    return {
        "session_id": task_id,
        "task_title": task_title or f"Automation: {payload.get('site') or task_id}",
        "current_goal": current_goal or "Run browser automation recipe",
        "status": status,
        "last_safe_step": last_safe_step,
        "next_step": next_step,
        "blocked_reason": blocked_reason if status == "blocked" else None,
        "requires_approval": requires_approval,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "automation": {
            "schema_version": payload.get("schema_version"),
            "site": payload.get("site"),
            "final_url": payload.get("final_url"),
            "completed_steps": completed_steps,
            "artifacts": payload.get("artifacts") or {},
            "checkpoint": payload.get("checkpoint"),
            "blocker": payload.get("blocker"),
        },
    }


def write_automation_task_state(
    payload: Mapping[str, Any],
    *,
    task_state_dir: str | Path,
    task_title: str | None = None,
    current_goal: str | None = None,
) -> AutomationTaskStateUpdate:
    """Write task-state YAML for an automation result."""

    state = state_from_automation_payload(
        payload,
        task_title=task_title,
        current_goal=current_goal,
    )
    task_id = str(state["session_id"])
    out_dir = Path(task_state_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{task_id}.yaml"
    path.write_text(yaml.safe_dump(state, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return AutomationTaskStateUpdate(path=path, state=state)
