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


def _shuffled_order(items: list[dict], seed: str | None) -> list[dict]:
    order = list(items)
    if seed is not None:
        random.Random(seed).shuffle(order)
    else:
        random.shuffle(order)
    return order


async def run_send_pv(
    client: "TelegramClient",
    message: str | None = None,
    delay_min: int | None = None,
    delay_max: int | None = None,
    *,
    start_from_index: int = 0,
    on_progress=None,
    shuffle_seed: str | None = None,
) -> None:
    """
    Send one message to each PV link (opens the chat). Calm delays between each.
    Supports resume via start_from_index, on_progress, shuffle_seed (avoids duplicate PMs on restart).
    """
    pv_list = get_pv_list()
    if not pv_list:
        logger.info("No PV in pool, skipping.")
        return
    msg = (message or PV_DEFAULT_MESSAGE).strip() or "سلام"
    delay_min = delay_min if delay_min is not None else DELAY_BETWEEN_JOINS_MIN
    delay_max = delay_max if delay_max is not None else DELAY_BETWEEN_JOINS_MAX
    order = _shuffled_order(pv_list, shuffle_seed)
    total = len(order)
    for i in range(start_from_index, total):
        p = order[i]
        link = p.get("link")
        if not link:
            if on_progress:
                on_progress(i + 1, total)
            continue
        try:
            entity = await client.get_entity(link)
            await client.send_message(entity, msg)
            logger.info("Sent PV to %s", link[:50])
        except Exception as e:
            logger.warning("PV failed for %s: %s", link[:50], e)
        if on_progress:
            on_progress(i + 1, total)
        if i < total - 1:
            wait = random.randint(delay_min, delay_max)
            logger.debug("Waiting %s s before next PV.", wait)
            await asyncio.sleep(wait)
