"""Tasks runner: use account sessions to complete Stars tasks calmly.

Per account and per task bot:
- Send /stars
- Read latest task message with buttons (Перейти / Подтвердить / Пропустить)
- Skip external links by clicking Пропустить
- For Telegram links: join channel/group or /start bot, then click Подтвердить
"""
import asyncio
import logging
import random
from pathlib import Path
from urllib.parse import urlparse

from telethon import TelegramClient, errors
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest

from core import db
from core.config import LOGS_DIR
from .config import (
    TASKS_LOG_FILE,
    MESSAGES_LIMIT,
    DELAY_AFTER_STARS_MIN,
    DELAY_AFTER_STARS_MAX,
    DELAY_BEFORE_CONFIRM_MIN,
    DELAY_BEFORE_CONFIRM_MAX,
    MAX_CONFIRM_ATTEMPTS,
)
from .data_loader import get_task_bots

logger = logging.getLogger("rezabots.tasks")


def _ensure_tasks_logger_configured() -> None:
    """Attach a dedicated file handler for tasks.log (idempotent)."""
    # Avoid duplicate handlers if called multiple times
    for h in logger.handlers:
        if isinstance(h, logging.FileHandler) and str(getattr(h, "baseFilename", "")).endswith("tasks.log"):
            return
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    TASKS_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(TASKS_LOG_FILE, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.info("Tasks logger initialized at %s", TASKS_LOG_FILE.resolve())


def _is_joinchat_link(link: str) -> bool:
    link = (link or "").strip()
    return "/joinchat/" in link or "/+" in link


def _extract_joinchat_hash(link: str) -> str | None:
    link = (link or "").strip()
    for prefix in ("https://t.me/joinchat/", "https://t.me/+", "t.me/joinchat/", "t.me/+"):
        if link.startswith(prefix):
            return link.split(prefix, 1)[1].split("?", 1)[0].strip()
    return None


def _is_telegram_link(url: str) -> bool:
    """True if URL points to Telegram (t.me / telegram.me / telegram.dog)."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host in {"t.me", "telegram.me", "telegram.dog"}


def _is_flood_error(exc: BaseException) -> bool:
    """Detect Telegram flood errors for cautious backoff."""
    try:
        if isinstance(exc, (errors.FloodWaitError, errors.PeerFloodError)):
            return True
        if getattr(errors, "FloodError", None) and isinstance(exc, errors.FloodError):
            return True
    except Exception:
        pass
    msg = str(exc).lower()
    return any(x in msg for x in ("flood", "peer_flood", "too many requests", "too many attempts", "slowmode"))


async def _find_task_message_with_buttons(client: TelegramClient, bot_entity) -> tuple | tuple[None, None, None, None]:
    """Return (message, go_button, confirm_button, skip_button) or (None, None, None, None)."""
    async for message in client.iter_messages(bot_entity, limit=MESSAGES_LIMIT):
        if not getattr(message, "buttons", None):
            continue
        go_button = None
        confirm_button = None
        skip_button = None
        for row in message.buttons:
            for button in row:
                text = (button.text or "").strip()
                if not text:
                    continue
                if "Перейти" in text and getattr(button, "url", None):
                    go_button = button
                elif "Подтвердить" in text:
                    confirm_button = button
                elif "Пропустить" in text:
                    skip_button = button
        if go_button and (confirm_button or skip_button):
            return message, go_button, confirm_button, skip_button
    return None, None, None, None


async def _check_task_success(client: TelegramClient, bot_entity, original_msg_id: int) -> bool:
    """Heuristic: message deleted or new message starts with '✅ Задание выполнено!'."""
    try:
        msgs = await client.get_messages(bot_entity, ids=[original_msg_id])
        if not msgs:
            return True
        msg = msgs[0]
        if msg is None or getattr(msg, "message", None) is None:
            return True
    except Exception:
        # If we cannot fetch the message, assume it might be deleted/successful
        return True

    async for m in client.iter_messages(bot_entity, limit=5):
        text = (m.text or "") if getattr(m, "text", None) else ""
        if text.startswith("✅ Задание выполнено!"):
            return True
    return False


async def _perform_telegram_task(client: TelegramClient, url: str, session_name: str) -> None:
    """Join channel/group or /start bot based on Telegram link."""
    url = (url or "").strip()
    if not url:
        return
    try:
        if _is_joinchat_link(url):
            hash_part = _extract_joinchat_hash(url)
            if hash_part:
                await client(ImportChatInviteRequest(hash_part))
                logger.info("[%s] Joined via invite: %s", session_name, url[:80])
                return
        # For normal t.me links, let Telethon resolve entity
        entity = await client.get_entity(url)
        # If it's a bot user → send /start
        if getattr(entity, "bot", False):
            await client.send_message(entity, "/start")
            logger.info("[%s] Sent /start to bot from %s", session_name, url[:80])
        else:
            await client(JoinChannelRequest(entity))
            logger.info("[%s] Joined channel/chat from %s", session_name, url[:80])
    except Exception as e:
        logger.warning("[%s] Telegram task failed for %s: %s", session_name, url[:80], e)


async def _run_tasks_for_bot(
    client: TelegramClient,
    bot_link: str,
    session_name: str,
) -> None:
    """Single account + single task bot flow."""
    bot_link = (bot_link or "").strip()
    if not bot_link:
        return
    try:
        bot_entity = await client.get_entity(bot_link)
    except Exception as e:
        logger.warning("[%s] Could not resolve task bot %s: %s", session_name, bot_link, e)
        return

    try:
        await client.send_message(bot_entity, "/stars")
        logger.info("[%s] Sent /stars to %s", session_name, bot_link)
    except Exception as e:
        logger.warning("[%s] Failed to send /stars to %s: %s", session_name, bot_link, e)
        return

    await asyncio.sleep(random.uniform(DELAY_AFTER_STARS_MIN, DELAY_AFTER_STARS_MAX))

    message, go_button, confirm_button, skip_button = await _find_task_message_with_buttons(client, bot_entity)
    if not message or not go_button:
        logger.info("[%s] No task message with buttons found for bot %s", session_name, bot_link)
        return

    url = getattr(go_button, "url", None) or ""
    if not url:
        logger.info("[%s] Task message has no URL button for bot %s", session_name, bot_link)
        return

    if not _is_telegram_link(url):
        # External link → only click Пропустить
        if skip_button:
            try:
                await skip_button.click()
                logger.info("[%s] Skipped external task link for bot %s: %s", session_name, bot_link, url)
            except Exception as e:
                logger.warning("[%s] Failed to click skip for external link %s: %s", session_name, url, e)
        else:
            logger.info("[%s] External task link but no skip button, bot=%s url=%s", session_name, bot_link, url)
        return

    # Telegram link: perform the task, then confirm
    await _perform_telegram_task(client, url, session_name)
    await asyncio.sleep(random.uniform(DELAY_BEFORE_CONFIRM_MIN, DELAY_BEFORE_CONFIRM_MAX))

    if not confirm_button:
        logger.info("[%s] No confirm button for Telegram task link, bot=%s url=%s", session_name, bot_link, url)
        return

    for attempt in range(1, MAX_CONFIRM_ATTEMPTS + 1):
        try:
            await confirm_button.click()
            logger.info(
                "[%s] Clicked confirm (attempt %s) for bot=%s url=%s",
                session_name,
                attempt,
                bot_link,
                url,
            )
        except Exception as e:
            logger.warning(
                "[%s] Confirm click failed (attempt %s) for bot=%s url=%s: %s",
                session_name,
                attempt,
                bot_link,
                url,
                e,
            )
        await asyncio.sleep(random.uniform(DELAY_BEFORE_CONFIRM_MIN, DELAY_BEFORE_CONFIRM_MAX))
        try:
            ok = await _check_task_success(client, bot_entity, message.id)
        except Exception:
            ok = False
        if ok:
            logger.info("[%s] Task confirmed successfully for bot=%s url=%s", session_name, bot_link, url)
            return

    logger.info(
        "[%s] Confirm did not succeed after %s attempts for bot=%s url=%s (will retry next cycle)",
        session_name,
        MAX_CONFIRM_ATTEMPTS,
        bot_link,
        url,
    )


async def run_tasks_for_all_accounts(main_node_id_only: bool = True) -> None:
    """Entry point: load accounts and task bots, run tasks for each account."""
    _ensure_tasks_logger_configured()
    bots = get_task_bots(with_name=False)
    if not bots:
        logger.info("No task bots configured in tasks_links.json; skipping tasks run.")
        return

    if main_node_id_only:
        main_id = await db.get_main_node_id()
        if not main_id:
            logger.warning("No main node in DB, skipping tasks run.")
            return
        accounts = await db.list_accounts(node_id=main_id)
    else:
        accounts = await db.list_accounts()

    if not accounts:
        logger.info("No accounts in DB for tasks run.")
        return

    logger.info("Starting tasks run for %s account(s) and %s task bot(s).", len(accounts), len(bots))

    for acc in accounts:
        aid = acc.get("id")
        phone = (acc.get("phone") or "")[:10]
        session_path = acc.get("session_path")
        api_id = acc.get("api_id")
        api_hash = acc.get("api_hash")
        if not session_path or not api_id or not api_hash:
            logger.warning("Account id=%s phone=%s missing session_path/api_id/api_hash, skip.", aid, phone)
            continue

        session_name = Path(session_path).stem or phone or str(aid or "")
        client = TelegramClient(session_path, int(api_id), api_hash or "")
        try:
            await client.connect()
            if not await client.is_user_authorized():
                logger.warning("[%s] Session not authorized, skipping account id=%s", session_name, aid)
                await client.disconnect()
                continue
            logger.info("[%s] Tasks: starting for account id=%s phone=%s", session_name, aid, phone)
            for bot in bots:
                link = bot.get("link")
                if not link:
                    continue
                await _run_tasks_for_bot(client, link, session_name)
        except Exception as e:
            if _is_flood_error(e):
                logger.warning(
                    "[%s] Flood error during tasks for account id=%s phone=%s: %s — skipping this account.",
                    session_name,
                    aid,
                    phone,
                    e,
                )
            else:
                logger.exception(
                    "[%s] Tasks failed for account id=%s phone=%s: %s",
                    session_name,
                    aid,
                    phone,
                    e,
                )
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

    logger.info("Tasks run finished for all accounts.")

