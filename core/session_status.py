"""Check if a Telethon session is active; add account as channel admin."""
import logging

from telethon import TelegramClient
from telethon.tl.functions.channels import EditAdminRequest
from telethon.tl.types import ChatAdminRights

logger = logging.getLogger(__name__)


async def add_account_as_channel_admin(
    session_path: str,
    api_id: int,
    api_hash: str,
    channel_id: int,
) -> tuple[bool, str]:
    """
    Use the account's session to add itself (me) as admin in the channel.
    Returns (success, error_message). Error is empty on success.
    """
    try:
        client = TelegramClient(session_path, api_id, api_hash)
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return False, "Session not authorized"
        me = await client.get_me()
        if not me:
            await client.disconnect()
            return False, "Could not get user"
        channel = await client.get_entity(channel_id)
        rights = ChatAdminRights(
            change_info=True,
            post_messages=True,
            edit_messages=True,
            delete_messages=True,
            ban_users=True,
            invite_users=True,
            pin_messages=True,
            add_admins=True,
            manage_call=True,
        )
        await client(EditAdminRequest(channel=channel, user_id=me, admin_rights=rights, rank="Admin"))
        await client.disconnect()
        return True, ""
    except Exception as e:
        logger.warning("Add account as channel admin failed: %s", e)
        return False, str(e)[:100]


async def check_session_status(
    session_path: str,
    api_id: int,
    api_hash: str,
) -> tuple[bool, str | None]:
    """
    Check if session is active. Returns (is_active, error_message).
    error_message is None when active, or a short error string when not.
    """
    try:
        client = TelegramClient(session_path, api_id, api_hash)
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return False, "Session not authorized"
        me = await client.get_me()
        await client.disconnect()
        if me:
            return True, None
        return False, "Could not get user"
    except Exception as e:
        logger.warning("Session check failed for %s: %s", session_path, e)
        return False, str(e)[:100]
