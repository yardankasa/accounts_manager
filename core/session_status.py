"""Check if a Telethon session is active (authorized and reachable)."""
import logging

from telethon import TelegramClient

logger = logging.getLogger(__name__)


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
