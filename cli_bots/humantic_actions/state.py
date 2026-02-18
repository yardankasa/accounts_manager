"""
Resume state for humantic actions. If the script crashes, the next run
continues from the last saved position so we never re-join or re-send PV.
"""
import json
import logging
import time
from pathlib import Path
from typing import Any

from .config import STATE_FILE, RESUME_MAX_AGE_SECONDS

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())


def load_state() -> dict[str, Any] | None:
    """
    Load state from file. Returns None if file missing or invalid.
    State shape: {
      "run_id": "2025-02-18T12:00:00",
      "completed_account_ids": [1, 2],
      "current": {"account_id": 3, "step": "chats", "index": 2}  # or null
    }
    """
    if not STATE_FILE.exists():
        return None
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "run_id" not in data:
            return None
        return data
    except Exception as e:
        logger.warning("Could not load state from %s: %s", STATE_FILE, e)
        return None


def state_is_recent(state: dict[str, Any]) -> bool:
    """True if state.run_id is within RESUME_MAX_AGE_SECONDS."""
    run_id = state.get("run_id")
    if not run_id:
        return False
    try:
        # Parse ISO-ish "2025-02-18T12:00:00"
        t = time.strptime(run_id[:19], "%Y-%m-%dT%H:%M:%S")
        ts = time.mktime(t)
        return (time.time() - ts) < RESUME_MAX_AGE_SECONDS
    except Exception:
        return False


def save_state(
    run_id: str,
    completed_account_ids: list[int],
    current: dict[str, Any] | None,
) -> None:
    """Write state to file. current = {account_id, step, index} or None."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "run_id": run_id,
        "completed_account_ids": completed_account_ids,
        "current": current,
    }
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.warning("Could not save state to %s: %s", STATE_FILE, e)


def clear_state() -> None:
    """Remove state file (e.g. after successful full run)."""
    try:
        if STATE_FILE.exists():
            STATE_FILE.unlink()
            logger.info("Cleared resume state.")
    except Exception as e:
        logger.warning("Could not clear state file %s: %s", STATE_FILE, e)
