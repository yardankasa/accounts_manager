"""
Humantic actions runner: one flow per account, all accounts sequential.
Reads accounts from DB (main node only in v1), then for each account:
  join channels (calm) → wait → join chats (calm) → wait → send PV (calm).
If the script crashes, the next run RESUMES from the last saved position:
  no re-join, no duplicate PV — safe.
"""
import asyncio
import logging
import random
import sys
from pathlib import Path

from telethon import TelegramClient

from .channels import run_join_channels
from .chats import run_join_chats
from .pv import run_send_pv
from .config import DELAY_BETWEEN_STEPS_MIN, DELAY_BETWEEN_STEPS_MAX
from .state import load_state, save_state, clear_state, state_is_recent

logger = logging.getLogger(__name__)

# App root for imports
_APP_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

STEP_ORDER = ("channels", "chats", "pv")


def _run_id_now() -> str:
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())


async def run_humantic_for_client(
    client: TelegramClient,
    account_id: int,
    run_id: str,
    resume: dict | None,
    on_persist=None,
) -> None:
    """
    Run full humantic flow for one account: channels → chats → PV.
    resume = { "step": "channels"|"chats"|"pv", "index": int } to continue from a crash.
    on_persist(account_id, step, next_index) is called after each action so runner can save state.
    """
    seed = f"{run_id}_{account_id}"
    delay_min, delay_max = DELAY_BETWEEN_STEPS_MIN, DELAY_BETWEEN_STEPS_MAX

    def _progress(step: str, next_index: int) -> None:
        if on_persist:
            on_persist(account_id, step, next_index)

    # Which step to start from and at which index
    start_step = 0
    start_index = 0
    if resume and resume.get("step") in STEP_ORDER and isinstance(resume.get("index"), int):
        for i, s in enumerate(STEP_ORDER):
            if s == resume["step"]:
                start_step = i
                start_index = max(0, resume["index"])
                break

    # Step 1 — channels
    if start_step <= 0:
        logger.info("Humantic: step 1 — join channels (from index %s)", start_index if start_step == 0 else 0)
        await run_join_channels(
            client,
            start_from_index=start_index if start_step == 0 else 0,
            on_progress=lambda idx, total: _progress("channels", idx),
            shuffle_seed=seed,
        )
    else:
        logger.info("Humantic: step 1 — join channels (skipped, resuming later step)")
    wait = random.randint(delay_min, delay_max)
    logger.debug("Humantic: waiting %s s before chats.", wait)
    await asyncio.sleep(wait)

    # Step 2 — chats
    if start_step <= 1:
        start_chats = start_index if start_step == 1 else 0
        logger.info("Humantic: step 2 — join chats (from index %s)", start_chats)
        await run_join_chats(
            client,
            start_from_index=start_chats,
            on_progress=lambda idx, total: _progress("chats", idx),
            shuffle_seed=seed,
        )
    else:
        logger.info("Humantic: step 2 — join chats (skipped)")
    wait = random.randint(delay_min, delay_max)
    logger.debug("Humantic: waiting %s s before PV.", wait)
    await asyncio.sleep(wait)

    # Step 3 — PV
    if start_step <= 2:
        start_pv = start_index if start_step == 2 else 0
        logger.info("Humantic: step 3 — send PV (from index %s)", start_pv)
        await run_send_pv(
            client,
            start_from_index=start_pv,
            on_progress=lambda idx, total: _progress("pv", idx),
            shuffle_seed=seed,
        )
    else:
        logger.info("Humantic: step 3 — send PV (skipped)")
    # Account fully done
    if on_persist:
        on_persist(account_id, "done", 0)


async def run_all_accounts(main_node_id_only: bool = True) -> None:
    """
    Load accounts from DB and run humantic flow for each, one by one.
    If a previous run crashed, state is resumed (no duplicate joins/PV).
    State is only used when it's from a run started within RESUME_MAX_AGE (e.g. 2h).
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

    # Resume state: skip completed accounts and resume from current step/index if recent
    state = load_state()
    run_id: str
    completed_ids: list[int]
    current: dict | None

    if state and state_is_recent(state):
        run_id = state["run_id"]
        completed_ids = list(state.get("completed_account_ids") or [])
        current = state.get("current")
        logger.info("Resuming run %s: %s account(s) already done, current=%s", run_id, len(completed_ids), current)
    else:
        run_id = _run_id_now()
        completed_ids = []
        current = None
        save_state(run_id, completed_ids, None)
        logger.info("New run %s for %s account(s).", run_id, len(accounts))

    # Skip accounts without credentials
    account_ids = [acc["id"] for acc in accounts if acc.get("session_path") and acc.get("api_id") and acc.get("api_hash")]

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

        # Resume this account from saved step/index?
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
            await run_humantic_for_client(client, aid, run_id, resume, on_persist=persist)
            logger.info("Humantic: finished for account phone=%s", phone)
        except Exception as e:
            logger.exception("Humantic failed for account phone=%s: %s", phone, e)
            # State already saved after last successful action; next run will resume from there
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

    # Run finished (we iterated all accounts) — clear state so next run is a fresh one
    clear_state()
    logger.info("Humantic: all accounts done.")


def main_sync() -> None:
    """Synchronous entry: init DB, run all accounts, close DB. Supports resume on next run if this one crashes."""
    import asyncio
    from core import db

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logger.info("Humantic actions v1 — starting (resume-safe).")

    async def _run() -> None:
        await db.init_pool()
        try:
            await run_all_accounts(main_node_id_only=True)
        finally:
            await db.close_pool()

    asyncio.run(_run())
    logger.info("Humantic actions v1 — finished.")


if __name__ == "__main__":
    main_sync()
