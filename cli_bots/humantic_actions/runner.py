"""
Humantic actions runner: one flow per account, all accounts sequential.
Reads accounts from DB (main node only in v1), then for each account:
  join channels (calm) → wait → join chats (calm) → wait → send PV (calm).
Then move to next account. All sync and calm.
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

logger = logging.getLogger(__name__)

# App root for imports
_APP_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))


async def run_humantic_for_client(client: TelegramClient) -> None:
    """
    Run full humantic flow for one account: channels → chats → PV.
    Calm delays between each step.
    """
    logger.info("Humantic: step 1 — join channels")
    await run_join_channels(client)

    wait = random.randint(DELAY_BETWEEN_STEPS_MIN, DELAY_BETWEEN_STEPS_MAX)
    logger.info("Humantic: waiting %s s before chats.", wait)
    await asyncio.sleep(wait)

    logger.info("Humantic: step 2 — join chats")
    await run_join_chats(client)

    wait = random.randint(DELAY_BETWEEN_STEPS_MIN, DELAY_BETWEEN_STEPS_MAX)
    logger.info("Humantic: waiting %s s before PV.", wait)
    await asyncio.sleep(wait)

    logger.info("Humantic: step 3 — send PV")
    await run_send_pv(client)


async def run_all_accounts(main_node_id_only: bool = True) -> None:
    """
    Load accounts from DB and run humantic flow for each, one by one.
    In v1 we only run for accounts on the main node (session files local).
    Skips accounts without api_id/api_hash.
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

    logger.info("Humantic: running for %s account(s), one by one.", len(accounts))

    for acc in accounts:
        session_path = acc.get("session_path")
        api_id = acc.get("api_id")
        api_hash = acc.get("api_hash")
        phone = (acc.get("phone") or "")[:8]
        if not session_path or not api_id or not api_hash:
            logger.warning("Account id=%s phone=%s missing session_path/api_id/api_hash, skip.", acc.get("id"), phone)
            continue

        client = TelegramClient(session_path, int(api_id), api_hash or "")
        try:
            await client.connect()
            if not await client.is_user_authorized():
                logger.warning("Account phone=%s not authorized, skip.", phone)
                await client.disconnect()
                continue
            logger.info("Humantic: starting for account phone=%s", phone)
            await run_humantic_for_client(client)
            logger.info("Humantic: finished for account phone=%s", phone)
        except Exception as e:
            logger.exception("Humantic failed for account phone=%s: %s", phone, e)
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

    logger.info("Humantic: all accounts done.")


def main_sync() -> None:
    """Synchronous entry: init DB, run all accounts, close DB."""
    import asyncio
    from core import db

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logger.info("Humantic actions v1 — starting.")

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
