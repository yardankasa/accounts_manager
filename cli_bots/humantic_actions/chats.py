"""
Humantic actions: join chats (groups/supergroups) in random order with calm delays.
"""
import asyncio
import logging
import random
from typing import TYPE_CHECKING

from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest

from .config import DELAY_BETWEEN_JOINS_MIN, DELAY_BETWEEN_JOINS_MAX
from .data_loader import get_chats_list

if TYPE_CHECKING:
    from telethon import TelegramClient

logger = logging.getLogger(__name__)


def _is_joinchat_link(link: str) -> bool:
    return "/joinchat/" in link or "/+" in link


def _extract_joinchat_hash(link: str) -> str | None:
    link = link.strip()
    for prefix in ("https://t.me/joinchat/", "https://t.me/+", "t.me/joinchat/", "t.me/+"):
        if link.startswith(prefix):
            return link.split(prefix, 1)[1].split("?")[0].strip()
    return None


async def _join_one(client: "TelegramClient", link: str) -> bool:
    try:
        if _is_joinchat_link(link):
            hash_part = _extract_joinchat_hash(link)
            if not hash_part:
                logger.warning("Could not parse joinchat link: %s", link[:50])
                return False
            await client(ImportChatInviteRequest(hash_part))
            logger.info("Joined chat (invite): %s", link[:50])
        else:
            entity = await client.get_entity(link)
            await client(JoinChannelRequest(entity))
            logger.info("Joined chat: %s", link[:50])
        return True
    except Exception as e:
        err = str(e).lower()
        if "already" in err or "participant" in err or "invite" in err:
            logger.debug("Already in or invite issue for %s: %s", link[:50], e)
            return True
        logger.warning("Join chat failed for %s: %s", link[:50], e)
        return False


def _shuffled_order(items: list[dict], seed: str | None) -> list[dict]:
    order = list(items)
    if seed is not None:
        random.Random(seed).shuffle(order)
    else:
        random.shuffle(order)
    return order


async def run_join_chats(
    client: "TelegramClient",
    delay_min: int | None = None,
    delay_max: int | None = None,
    *,
    start_from_index: int = 0,
    on_progress=None,
    shuffle_seed: str | None = None,
) -> None:
    """Join all chats from links pool in random order, with calm delays. Supports resume via start_from_index, on_progress, shuffle_seed."""
    chats = get_chats_list()
    if not chats:
        logger.info("No chats in pool, skipping.")
        return
    delay_min = delay_min if delay_min is not None else DELAY_BETWEEN_JOINS_MIN
    delay_max = delay_max if delay_max is not None else DELAY_BETWEEN_JOINS_MAX
    order = _shuffled_order(chats, shuffle_seed)
    total = len(order)
    for i in range(start_from_index, total):
        c = order[i]
        link = c.get("link")
        if not link:
            if on_progress:
                on_progress(i + 1, total)
            continue
        await _join_one(client, link)
        if on_progress:
            on_progress(i + 1, total)
        if i < total - 1:
            wait = random.randint(delay_min, delay_max)
            logger.debug("Waiting %s s before next chat.", wait)
            await asyncio.sleep(wait)
