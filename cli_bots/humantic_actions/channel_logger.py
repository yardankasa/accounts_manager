"""
Log all humantic actions and run lifecycle to IM_ALIVE_CHANNEL_ID using BOT_TOKEN.
Full detail per action: account, action type, link, time, status.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)

# Persian labels for action types
ACTION_LABELS = {
    "join_channel": "عضویت در کانال",
    "join_chat": "عضویت در گروه",
    "send_pv": "ارسال پیام خصوصی",
    "leave_channel": "ترک کانال",
    "leave_chat": "ترک گروه",
}


def _action_label(action_type: str) -> str:
    return ACTION_LABELS.get(action_type, action_type)


def make_channel_logger(bot: Any = None) -> Callable[[str], Awaitable[None]] | None:
    """
    Return an async log function that sends messages to IM_ALIVE_CHANNEL_ID using the bot.
    If bot is None, create one from BOT_TOKEN (for CLI). Returns None if channel or token not set.
    """
    import sys
    from pathlib import Path
    _root = Path(__file__).resolve().parent.parent.parent
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
    from core.config import BOT_TOKEN, IM_ALIVE_CHANNEL_ID
    if not IM_ALIVE_CHANNEL_ID or not BOT_TOKEN:
        return None
    try:
        channel_id = int(IM_ALIVE_CHANNEL_ID.strip())
    except ValueError:
        return None
    _bot = bot
    if _bot is None:
        try:
            from telegram import Bot
            _bot = Bot(token=BOT_TOKEN)
        except Exception as e:
            logger.warning("Could not create Bot for humantic log: %s", e)
            return None

    async def log_message(text: str) -> None:
        try:
            await _bot.send_message(chat_id=channel_id, text=text)
        except Exception as e:
            logger.warning("Humantic log to channel failed: %s", e)

    return log_message


def format_run_start(run_id: str, total_accounts: int) -> str:
    return (
        "🤖 رفتار انسانی — شروع اجرا\n"
        f"شناسه اجرا: {run_id}\n"
        f"تعداد اکانت‌ها: {total_accounts}\n"
        f"زمان: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )


def format_run_end(run_id: str, completed: int) -> str:
    return (
        "🤖 رفتار انسانی — پایان اجرا\n"
        f"شناسه اجرا: {run_id}\n"
        f"اکانت‌های انجام‌شده: {completed}\n"
        f"زمان: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )


def format_account_start(account_id: int, phone: str) -> str:
    return (
        "▶️ شروع اکانت\n"
        f"شناسه اکانت: {account_id}\n"
        f"شماره: {phone}\n"
        f"زمان: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )


def format_account_end(account_id: int, phone: str, success: bool) -> str:
    status = "✅ موفق" if success else "❌ با خطا"
    return (
        "⏹ پایان اکانت\n"
        f"شناسه اکانت: {account_id}\n"
        f"شماره: {phone}\n"
        f"وضعیت: {status}\n"
        f"زمان: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )


def format_action(account_id: int, phone: str, action_type: str, link: str, success: bool, error_msg: str | None = None) -> str:
    label = _action_label(action_type)
    status = "✅ موفق" if success else f"❌ خطا: {error_msg or 'نامشخص'}"
    link_short = link[:60] + "…" if len(link) > 60 else link
    return (
        "📌 عملیات\n"
        f"اکانت: id={account_id} | {phone}\n"
        f"نوع: {label}\n"
        f"لینک: {link_short}\n"
        f"وضعیت: {status}\n"
        f"زمان: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )
