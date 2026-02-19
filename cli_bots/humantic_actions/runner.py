"""
Humantic actions runner: one interleaved action queue per account (no fixed order).
Actions: join channel, join chat, send PV, leave channel, leave chat — shuffled randomly.
If the script crashes, the next run resumes from the last saved action index.
"""
import asyncio
import logging
import random
import sys
from pathlib import Path

from telethon import TelegramClient

from .actions import build_action_list, run_one_action
from .config import DELAY_BETWEEN_JOINS_MIN, DELAY_BETWEEN_JOINS_MAX
from .state import load_state, save_state, clear_state, state_is_recent

logger = logging.getLogger(__name__)

_APP_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

# Resume state uses step "actions" and index = action index in the shuffled list
RESUME_STEP_ACTIONS = "actions"


def _run_id_now() -> str:
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())


async def run_humantic_for_client(
    client: TelegramClient,
    account_id: int,
    run_id: str,
    resume: dict | None,
    on_persist=None,
    include_leave: bool = True,
) -> None:
    """
    Run one shuffled action list for this account: join/leave channels, join/leave chats, send PV — random order.
    resume = { "step": "actions", "index": int } to continue from a crash.
    """
    seed = f"{run_id}_{account_id}"
    action_list = build_action_list(seed, include_leave=include_leave)
    if not action_list:
        logger.info("No actions in pool for account id=%s.", account_id)
        if on_persist:
            on_persist(account_id, "done", 0)
        return

    start_index = 0
    if resume and resume.get("step") == RESUME_STEP_ACTIONS and isinstance(resume.get("index"), int):
        start_index = max(0, resume["index"])
        logger.info("Resuming from action index %s / %s", start_index, len(action_list))

    delay_min, delay_max = DELAY_BETWEEN_JOINS_MIN, DELAY_BETWEEN_JOINS_MAX
    for i in range(start_index, len(action_list)):
        action_type, link = action_list[i]
        await run_one_action(client, action_type, link)
        if on_persist:
            on_persist(account_id, RESUME_STEP_ACTIONS, i + 1)
        if i < len(action_list) - 1:
            wait = random.randint(delay_min, delay_max)
            await asyncio.sleep(wait)

    if on_persist:
        on_persist(account_id, "done", 0)


async def run_all_accounts(
    main_node_id_only: bool = True,
    include_leave: bool = True,
) -> None:
    """
    Load accounts from DB and run humantic flow for each, one by one.
    If a previous run crashed, state is resumed from last action index.
    """
    from core import db

    if main_node_id_only:
        main_id = await db.get_main_node_id()
        if not main_id:
            logger.warning("No main node in DB, skipping humantic run.")
            return
        accounts = await db.list_accounts(node_id=main_id)
    else:
        accounts = await db.list_accounts()

    if not accounts:
        logger.info("No accounts in DB for humantic run.")
        return

    state = load_state()
    run_id: str
    completed_ids: list[int]
    current: dict | None

    if state and state_is_recent(state):
        run_id = state["run_id"]
        completed_ids = list(state.get("completed_account_ids") or [])
        current = state.get("current")
        logger.info("Resuming run %s: %s account(s) done, current=%s", run_id, len(completed_ids), current)
    else:
        run_id = _run_id_now()
        completed_ids = []
        current = None
        save_state(run_id, completed_ids, None)
        logger.info("New run %s for %s account(s), interleaved actions (include_leave=%s).", run_id, len(accounts), include_leave)

    def persist(account_id: int, step: str, index: int) -> None:
        if step == "done":
            completed_ids.append(account_id)
            save_state(run_id, completed_ids, None)
            logger.info("Humantic: account id=%s finished; %s completed so far.", account_id, len(completed_ids))
        else:
            save_state(run_id, completed_ids, {"account_id": account_id, "step": step, "index": index})

    for acc in accounts:
        aid = acc.get("id")
        if aid is None or aid in completed_ids:
            continue
        session_path = acc.get("session_path")
        api_id = acc.get("api_id")
        api_hash = acc.get("api_hash")
        phone = (acc.get("phone") or "")[:8]
        if not session_path or not api_id or not api_hash:
            logger.warning("Account id=%s phone=%s missing session_path/api_id/api_hash, skip.", aid, phone)
            continue

        resume = None
        if current and current.get("account_id") == aid:
            resume = {"step": current.get("step"), "index": current.get("index", 0)}
            logger.info("Resuming account id=%s from step=%s index=%s", aid, resume.get("step"), resume.get("index"))

        client = TelegramClient(session_path, int(api_id), api_hash or "")
        try:
            await client.connect()
            if not await client.is_user_authorized():
                logger.warning("Account phone=%s not authorized, skip.", phone)
                await client.disconnect()
                continue
            logger.info("Humantic: starting for account id=%s phone=%s", aid, phone)
            await run_humantic_for_client(client, aid, run_id, resume, on_persist=persist, include_leave=include_leave)
            logger.info("Humantic: finished for account phone=%s", phone)
        except Exception as e:
            logger.exception("Humantic failed for account phone=%s: %s", phone, e)
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

    clear_state()
    logger.info("Humantic: all accounts done.")


def main_sync(include_leave: bool = True) -> None:
    """Synchronous entry: init DB, run all accounts, close DB."""
    import asyncio
    from core import db

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logger.info("Humantic actions v1 — starting (interleaved, resume-safe).")

    async def _run() -> None:
        await db.init_pool()
        try:
            await run_all_accounts(main_node_id_only=True, include_leave=include_leave)
        finally:
            await db.close_pool()

    asyncio.run(_run())
    logger.info("Humantic actions v1 — finished.")


if __name__ == "__main__":
    main_sync()
