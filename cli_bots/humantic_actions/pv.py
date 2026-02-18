"""
Humantic actions: send one calm PM to each PV (private) link from the pool.
Opens the conversation like a normal user would.
"""
import asyncio
import logging
import random
from typing import TYPE_CHECKING

from .config import DELAY_BETWEEN_JOINS_MIN, DELAY_BETWEEN_JOINS_MAX, PV_DEFAULT_MESSAGE
from .data_loader import get_pv_list

if TYPE_CHECKING:
    from telethon import TelegramClient

logger = logging.getLogger(__name__)


async def run_send_pv(
    client: "TelegramClient",
    message: str | None = None,
    delay_min: int | None = None,
    delay_max: int | None = None,
) -> None:
    """
    Send one message to each PV link (opens the chat). Calm delays between each.
    Uses PV_DEFAULT_MESSAGE if message is not provided.
    """
    pv_list = get_pv_list()
    if not pv_list:
        logger.info("No PV in pool, skipping.")
        return
    msg = (message or PV_DEFAULT_MESSAGE).strip() or "سلام"
    delay_min = delay_min if delay_min is not None else DELAY_BETWEEN_JOINS_MIN
    delay_max = delay_max if delay_max is not None else DELAY_BETWEEN_JOINS_MAX
    order = list(pv_list)
    random.shuffle(order)
    for i, p in enumerate(order):
        link = p.get("link")
        if not link:
            continue
        try:
            # get_entity works with t.me/username for users
            entity = await client.get_entity(link)
            await client.send_message(entity, msg)
            logger.info("Sent PV to %s", link[:50])
        except Exception as e:
            logger.warning("PV failed for %s: %s", link[:50], e)
        if i < len(order) - 1:
            wait = random.randint(delay_min, delay_max)
            logger.debug("Waiting %s s before next PV.", wait)
            await asyncio.sleep(wait)
