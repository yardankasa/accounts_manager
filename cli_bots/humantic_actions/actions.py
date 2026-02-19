"""
Single humantic actions: join/leave channel or chat, send PV.
Used to build a random interleaved queue (no fixed order).
"""
import logging
import random
from typing import TYPE_CHECKING

from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest

from .config import DELAY_BETWEEN_JOINS_MIN, DELAY_BETWEEN_JOINS_MAX, PV_DEFAULT_MESSAGE
from .data_loader import get_channels_list, get_chats_list, get_pv_list

if TYPE_CHECKING:
    from telethon import TelegramClient

logger = logging.getLogger(__name__)

ACTION_JOIN_CHANNEL = "join_channel"
ACTION_JOIN_CHAT = "join_chat"
ACTION_SEND_PV = "send_pv"
ACTION_LEAVE_CHANNEL = "leave_channel"
ACTION_LEAVE_CHAT = "leave_chat"


def _is_joinchat_link(link: str) -> bool:
    return "/joinchat/" in link or "/+" in link


def _extract_joinchat_hash(link: str) -> str | None:
    link = link.strip()
    for prefix in ("https://t.me/joinchat/", "https://t.me/+", "t.me/joinchat/", "t.me/+"):
        if link.startswith(prefix):
            return link.split(prefix, 1)[1].split("?")[0].strip()
    return None


def build_action_list(seed: str, include_leave: bool = True) -> list[tuple[str, str]]:
    """
    Build one flat list of (action_type, link) and shuffle with seed so order is reproducible.
    No fixed sequence: join channel, join chat, pv, leave channel, leave chat all interleaved randomly.
    """
    out: list[tuple[str, str]] = []
    for ch in get_channels_list():
        out.append((ACTION_JOIN_CHANNEL, ch["link"]))
    for c in get_chats_list():
        out.append((ACTION_JOIN_CHAT, c["link"]))
    for p in get_pv_list():
        out.append((ACTION_SEND_PV, p["link"]))
    if include_leave:
        for ch in get_channels_list():
            out.append((ACTION_LEAVE_CHANNEL, ch["link"]))
        for c in get_chats_list():
            out.append((ACTION_LEAVE_CHAT, c["link"]))
    random.Random(seed).shuffle(out)
    return out


async def run_one_action(client: "TelegramClient", action_type: str, link: str, pv_message: str | None = None) -> None:
    """Execute a single action (join/leave channel or chat, or send PV)."""
    if action_type == ACTION_JOIN_CHANNEL:
        try:
            if _is_joinchat_link(link):
                hash_part = _extract_joinchat_hash(link)
                if hash_part:
                    await client(ImportChatInviteRequest(hash_part))
                    logger.info("Joined (invite) channel: %s", link[:50])
            else:
                entity = await client.get_entity(link)
                await client(JoinChannelRequest(entity))
                logger.info("Joined channel: %s", link[:50])
        except Exception as e:
            if "already" in str(e).lower() or "participant" in str(e).lower():
                logger.debug("Already in channel %s", link[:50])
            else:
                logger.warning("Join channel failed for %s: %s", link[:50], e)

    elif action_type == ACTION_JOIN_CHAT:
        try:
            if _is_joinchat_link(link):
                hash_part = _extract_joinchat_hash(link)
                if hash_part:
                    await client(ImportChatInviteRequest(hash_part))
                    logger.info("Joined (invite) chat: %s", link[:50])
            else:
                entity = await client.get_entity(link)
                await client(JoinChannelRequest(entity))
                logger.info("Joined chat: %s", link[:50])
        except Exception as e:
            if "already" in str(e).lower() or "participant" in str(e).lower():
                logger.debug("Already in chat %s", link[:50])
            else:
                logger.warning("Join chat failed for %s: %s", link[:50], e)

    elif action_type == ACTION_SEND_PV:
        try:
            msg = (pv_message or PV_DEFAULT_MESSAGE).strip() or "سلام"
            entity = await client.get_entity(link)
            await client.send_message(entity, msg)
            logger.info("Sent PV to %s", link[:50])
        except Exception as e:
            logger.warning("PV failed for %s: %s", link[:50], e)

    elif action_type == ACTION_LEAVE_CHANNEL:
        try:
            entity = await client.get_entity(link)
            await client(LeaveChannelRequest(entity))
            logger.info("Left channel: %s", link[:50])
        except Exception as e:
            err = str(e).lower()
            if "not participant" in err or "left" in err:
                logger.debug("Already left or not in channel %s: %s", link[:50], e)
            else:
                logger.warning("Leave channel failed for %s: %s", link[:50], e)

    elif action_type == ACTION_LEAVE_CHAT:
        try:
            entity = await client.get_entity(link)
            await client(LeaveChannelRequest(entity))
            logger.info("Left chat: %s", link[:50])
        except Exception as e:
            err = str(e).lower()
            if "not participant" in err or "left" in err:
                logger.debug("Already left or not in chat %s: %s", link[:50], e)
            else:
                logger.warning("Leave chat failed for %s: %s", link[:50], e)

    else:
        logger.warning("Unknown action type: %s", action_type)
