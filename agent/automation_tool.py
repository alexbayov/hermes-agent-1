"""Adapter for invoking hermes-automation as a subprocess tool.

This keeps Playwright-heavy automation isolated behind the CLI JSON contract
(`hermes.automation.result.v1`) while giving the main Hermes agent a small,
testable Python boundary it can call from tool wiring or orchestration code.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "hermes.automation.result.v1"


class AutomationToolError(RuntimeError):
    """Raised when the automation subprocess cannot return a valid result."""


@dataclass(frozen=True)
class AutomationRunRequest:
    """Inputs for one hermes-automation recipe run."""

    recipe: str
    task_id: str
    fields: Mapping[str, Any] = field(default_factory=dict)
    state_dir: str = "state"
    artifacts_dir: str = "artifacts"
    headless: bool = True
    reset: bool = False
    executable_path: str | None = None
    include_actions: bool = True


@dataclass(frozen=True)
class AutomationRunResult:
    """Parsed automation JSON result."""

    payload: Mapping[str, Any]
    exit_code: int
    stdout: str
    stderr: str

    @property
    def status(self) -> str:
        return str(self.payload.get("status", ""))

    @property
    def success(self) -> bool:
        return bool(self.payload.get("success"))

    @property
    def blocked_reason(self) -> str | None:
        value = self.payload.get("blocked_reason")
        return str(value) if value else None


def _default_cwd() -> Path:
    # hermes-agent/agent/automation_tool.py → repo root
    return Path(__file__).resolve().parents[2]


def build_automation_command(
    request: AutomationRunRequest,
    *,
    python_executable: str | None = None,
) -> list[str]:
    """Build the subprocess command for hermes-automation CLI."""

    python_executable = python_executable or sys.executable
    cmd = [
        python_executable,
        "-m",
        "harness.cli",
        "run",
        "--recipe",
        request.recipe,
        "--task-id",
        request.task_id,
        "--fields",
        json.dumps(dict(request.fields), ensure_ascii=False),
        "--state-dir",
        request.state_dir,
        "--artifacts-dir",
        request.artifacts_dir,
        "--headless" if request.headless else "--no-headless",
    ]
    if request.reset:
        cmd.append("--reset")
    if request.executable_path:
        cmd.extend(["--executable-path", request.executable_path])
    if not request.include_actions:
        cmd.append("--no-actions")
    return cmd


def run_automation_recipe(
    request: AutomationRunRequest,
    *,
    cwd: str | Path | None = None,
    timeout_s: int = 900,
    python_executable: str | None = None,
) -> AutomationRunResult:
    """Run hermes-automation and parse its JSON result.

    Exit code 0 (`done`) and 2 (`blocked`) are both valid tool outcomes.
    Other exit codes or malformed JSON raise AutomationToolError.
    """

    repo_root = Path(cwd) if cwd is not None else _default_cwd()
    automation_cwd = repo_root / "hermes-automation"
    cmd = build_automation_command(request, python_executable=python_executable)

    proc = subprocess.run(
        cmd,
        cwd=str(automation_cwd),
        text=True,
        capture_output=True,
        timeout=timeout_s,
        check=False,
    )

    if proc.returncode not in {0, 2}:
        raise AutomationToolError(
            f"hermes-automation failed with exit code {proc.returncode}: {proc.stderr.strip()}"
        )

    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise AutomationToolError(
            f"hermes-automation returned invalid JSON: {e}: {proc.stdout[:500]!r}"
        ) from e

    if payload.get("schema_version") != SCHEMA_VERSION:
        raise AutomationToolError(
            f"unexpected automation schema: {payload.get('schema_version')!r}"
        )

    return AutomationRunResult(
        payload=payload,
        exit_code=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def summarize_automation_result(result: AutomationRunResult) -> str:
    """Human-readable one-paragraph summary for Hermes responses/task state."""

    payload = result.payload
    status = payload.get("status")
    task_id = payload.get("task_id")
    site = payload.get("site")
    steps = payload.get("completed_steps") or []
    final_url = payload.get("final_url") or ""
    blocked_reason = payload.get("blocked_reason")
    error = payload.get("error")

    parts = [f"automation {status} for {task_id} on {site}"]
    if steps:
        parts.append(f"completed_steps={len(steps)}")
    if final_url:
        parts.append(f"final_url={final_url}")
    if blocked_reason:
        parts.append(f"blocked_reason={blocked_reason}")
    if error and not blocked_reason:
        parts.append(f"error={error}")
    return "; ".join(parts)
