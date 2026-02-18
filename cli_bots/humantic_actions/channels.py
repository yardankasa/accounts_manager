"""
Humantic actions: join channels in random order with calm delays.
Used to simulate a normal user and reduce ban risk.
"""
import asyncio
import logging
import random
from typing import TYPE_CHECKING

from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest

from .config import DELAY_BETWEEN_JOINS_MIN, DELAY_BETWEEN_JOINS_MAX
from .data_loader import get_channels_list

if TYPE_CHECKING:
    from telethon import TelegramClient

logger = logging.getLogger(__name__)


def _is_joinchat_link(link: str) -> bool:
    return "/joinchat/" in link or "/+" in link


def _extract_joinchat_hash(link: str) -> str | None:
    # e.g. https://t.me/joinchat/ABC123 or https://t.me/+ABC123
    link = link.strip()
    for prefix in ("https://t.me/joinchat/", "https://t.me/+", "t.me/joinchat/", "t.me/+"):
        if link.startswith(prefix):
            return link.split(prefix, 1)[1].split("?")[0].strip()
    return None


async def _join_one(client: "TelegramClient", link: str) -> bool:
    """Join one channel/chat by link. Returns True if joined or already in."""
    try:
        if _is_joinchat_link(link):
            hash_part = _extract_joinchat_hash(link)
            if not hash_part:
                logger.warning("Could not parse joinchat link: %s", link[:50])
                return False
            await client(ImportChatInviteRequest(hash_part))
            logger.info("Joined (invite): %s", link[:50])
        else:
            entity = await client.get_entity(link)
            await client(JoinChannelRequest(entity))
            logger.info("Joined: %s", link[:50])
        return True
    except Exception as e:
        # Already participant, or link invalid, etc.
        err = str(e).lower()
        if "already" in err or "participant" in err or "invite" in err:
            logger.debug("Already in or invite issue for %s: %s", link[:50], e)
            return True
        logger.warning("Join failed for %s: %s", link[:50], e)
        return False


async def run_join_channels(
    client: "TelegramClient",
    delay_min: int | None = None,
    delay_max: int | None = None,
) -> None:
    """
    Join all channels from links pool in random order, with calm delays.
    Safe to call multiple times (skips or no-ops if already in).
    """
    channels = get_channels_list()
    if not channels:
        logger.info("No channels in pool, skipping.")
        return
    delay_min = delay_min if delay_min is not None else DELAY_BETWEEN_JOINS_MIN
    delay_max = delay_max if delay_max is not None else DELAY_BETWEEN_JOINS_MAX
    order = list(channels)
    random.shuffle(order)
    for i, ch in enumerate(order):
        link = ch.get("link")
        if not link:
            continue
        await _join_one(client, link)
        if i < len(order) - 1:
            wait = random.randint(delay_min, delay_max)
            logger.debug("Waiting %s s before next channel.", wait)
            await asyncio.sleep(wait)
