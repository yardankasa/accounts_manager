"""
Grand policy: rules that apply to ALL running accounts.
Every account must pass these checks before performing an action;
actions that would violate a policy are delayed until allowed.

Important: limits are PER ACCOUNT. So 10 accounts running at the same time
can do up to 10 actions per second (one per account). We do not throttle globally.
"""
import asyncio
import logging
import time
from typing import Dict

logger = logging.getLogger(__name__)

# --- Policy 1: Maximum one action per account per second (per account, not global) ---
# Any action (reaction, send message, join, leave, API call, etc.) counts.
# Each account has its own clock: 10 accounts → up to 10 actions/sec total (1 per account).
_last_action_finish: Dict[int, float] = {}
_MIN_SECONDS_BETWEEN_ACTIONS = 1.0


async def apply_before_action(account_id: int) -> None:
    """
    Call before performing any single action for this account.
    Sleeps only if THIS account did an action less than 1 second ago.
    Other accounts are independent (e.g. 10 accounts = up to 10 actions in the same second).
    """
    now = time.monotonic()
    last = _last_action_finish.get(account_id)
    if last is not None:
        elapsed = now - last
        if elapsed < _MIN_SECONDS_BETWEEN_ACTIONS:
            wait = _MIN_SECONDS_BETWEEN_ACTIONS - elapsed
            logger.debug("Grand policy: account %s wait %.2f s (1 action/sec)", account_id, wait)
            await asyncio.sleep(wait)


def record_after_action(account_id: int) -> None:
    """
    Call after an action for this account has finished.
    Used so the next action will respect the 1 action/sec rule.
    """
    _last_action_finish[account_id] = time.monotonic()


def reset_account(account_id: int) -> None:
    """Clear policy state for an account (e.g. when switching accounts)."""
    _last_action_finish.pop(account_id, None)


def reset_all() -> None:
    """Clear all per-account state (e.g. at start of a new run)."""
    _last_action_finish.clear()
