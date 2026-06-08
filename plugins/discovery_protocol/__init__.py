"""Discovery Protocol Layer 3 plugin for Hermes Agent.

Injects protocol reminders into every LLM call via pre_llm_call hook.
No core patches needed.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

STATE_FILE = Path.home() / ".hermes" / "protocol_state.json"

# Alert templates injected as ephemeral user context
ALERT_NO_PLAN = (
    "[Discovery Protocol] Вы забыли задекларировать план. "
    "Пожалуйста, скажите: 'Приступаю к задаче. План: [1] ... [2] ... [3] ...' "
    "перед действием."
)
ALERT_STALLED = (
    "[Discovery Protocol] Задача заблокирована по протоколу. "
    "Ожидается уточнение от редактора. "
    "Не действуйте без его ответа."
)
ALERT_NO_DISCOVERY = (
    "[Discovery Protocol] Не завершена фаза разведки. "
    "Перед работой нужно: 1) уточнить запрос, 2) собрать контекст, 3) задекларировать план."
)


def _load_state() -> Dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _check_protocol(state: Dict[str, Any]) -> Optional[str]:
    """Return alert text if protocol violated, else None."""
    if not state.get("protocol_active", False):
        return None

    stage = state.get("stage", "idle")
    discovery_done = state.get("discovery_done", False)
    plan = state.get("current_plan")
    stalled_reason = state.get("stalled_reason")

    # Stalled = always alert
    if stage == "stalled" and stalled_reason:
        return ALERT_STALLED

    # No discovery done and trying to execute
    if not discovery_done and stage in ("executing", "reviewing", "planning"):
        return ALERT_NO_DISCOVERY

    # No plan but executing
    if stage in ("executing", "reviewing") and not plan:
        return ALERT_NO_PLAN

    return None


def on_pre_llm_call(
    session_id: str,
    user_message: str,
    conversation_history: List[Dict],
    is_first_turn: bool,
    model: str,
    platform: str,
    sender_id: str,
    **kwargs,
) -> Optional[str]:
    """pre_llm_call hook handler.

    Returns: string context to inject into user message, or None.
    """
    try:
        state = _load_state()
        alert = _check_protocol(state)
        if alert:
            logger.info("Discovery Protocol alert injected for session=%s stage=%s", session_id, state.get("stage"))
            return alert
    except Exception as exc:
        logger.warning("Discovery Protocol check failed: %s", exc)
    return None


def register(ctx) -> None:
    """Plugin entrypoint."""
    ctx.register_hook("pre_llm_call", on_pre_llm_call)
    logger.info("Discovery Protocol plugin registered (Layer 3 via pre_llm_call hook)")
