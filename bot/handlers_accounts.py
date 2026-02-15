"""Account list, delete, and status check."""
import logging
from datetime import datetime, timezone, timedelta
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler, filters

import core.db as db
from core.config import STATUS_CHANNEL_ID
from core.node_runner import check_node_connection, check_session_on_node

from .filters import ensure_admin
from .keyboards import account_list_inline, main_admin_keyboard
from .messages import MSG_ACCOUNTS_LIST, MSG_NO_ACCOUNTS, MSG_ACCOUNT_DELETED, MSG_ERROR_GENERIC
from .logging_utils import log_exception

logger = logging.getLogger(__name__)

# Tehran timezone: UTC+3:30
TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30))


def _mask_phone(phone: str) -> str:
    """Mask phone: +254123***456 (first 6 + *** + last 3 digits)."""
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) < 10:
        return "+***"
    return f"+{digits[:6]}***{digits[-3:]}"


def _format_status_report(
    phone: str,
    is_active: bool,
    checked_at: datetime,
    node_name: str,
    created_at: str | None,
    error: str = "",
) -> str:
    """Format account status report for channel."""
    masked = _mask_phone(phone)
    tehrantime = checked_at.astimezone(TEHRAN_TZ).strftime("%Y-%m-%d %H:%M:%S UTC+3:30")
    status = "✅ Active" if is_active else "❌ Not Active"
    if error and not is_active:
        status += f" ({error})"
    created_str = created_at or "—"
    return (
        f"📊 Account Status Report\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 Account: {masked}\n"
        f"🕐 Time checked: {tehrantime}\n"
        f"📡 Session status: {status}\n"
        f"📅 Time Account Login: {created_str}\n"
        f"🖥 Node: {node_name}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )


async def accounts_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_admin(update, context):
        return
    accounts = await db.list_accounts()
    if not accounts:
        await update.message.reply_text(MSG_NO_ACCOUNTS, reply_markup=main_admin_keyboard())
        return
    lines = []
    for a in accounts:
        line = f"شماره: {a.get('phone', '')} – نود: {a.get('node_name', '')}"

        lines.append(line)
    text = MSG_ACCOUNTS_LIST + "\n\n" + "\n".join(lines)
    kb = account_list_inline(accounts)
    await update.message.reply_text(text, reply_markup=kb)


async def account_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_admin(update, context):
        return
    q = update.callback_query
    await q.answer()
    if not q.data or not q.data.startswith("delacc_"):
        return
    try:
        account_id = int(q.data.split("_")[1])
    except (IndexError, ValueError):
        return
    acc = await db.get_account(account_id)
    if not acc:
        await q.edit_message_text(MSG_ACCOUNT_DELETED)
        return
    try:
        await db.delete_account(account_id)
        # Optionally delete session file on main or node
        node = await db.get_node(acc["node_id"])
        if node and node.get("is_main"):
            from pathlib import Path
            session_path = Path(acc["session_path"])
            if session_path.exists():
                for f in session_path.parent.glob(session_path.name + "*"):
                    try:
                        f.unlink()
                    except OSError:
                        pass
        await q.edit_message_text(MSG_ACCOUNT_DELETED)
    except Exception as e:
        log_exception(logger, "Delete account failed", e)
        await q.edit_message_text(MSG_ERROR_GENERIC)


async def account_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check account session status and send report to STATUS_CHANNEL_ID."""
    if not await ensure_admin(update, context):
        return
    q = update.callback_query
    await q.answer("در حال بررسی وضعیت...")
    if not q.data or not q.data.startswith("statusacc_"):
        return
    try:
        account_id = int(q.data.split("_")[1])
    except (IndexError, ValueError):
        await q.edit_message_text(MSG_ERROR_GENERIC)
        return
    acc = await db.get_account(account_id)
    if not acc:
        await q.edit_message_text("اکانت یافت نشد.")
        return
    api_id = acc.get("api_id")
    api_hash = acc.get("api_hash")
    if not api_id or not api_hash:
        await q.edit_message_text(
            "❌ API_ID و API_HASH این اکانت در دیتابیس ذخیره نشده.\n"
            "اکانت را دوباره وارد کنید تا ذخیره شود."
        )
        return
    if not STATUS_CHANNEL_ID:
        await q.edit_message_text(
            "❌ STATUS_CHANNEL_ID در .env تنظیم نشده.\n"
            "شناسه کانال/گروه را برای ارسال گزارش وارد کنید (مثال: -1001234567890)."
        )
        return
    try:
        channel_id = int(STATUS_CHANNEL_ID)
    except ValueError:
        await q.edit_message_text("❌ STATUS_CHANNEL_ID نامعتبر است.")
        return
    node = await db.get_node(acc["node_id"])
    if not node:
        await q.edit_message_text("نود اکانت یافت نشد.")
        return
    session_path = acc["session_path"]
    is_active, error = await check_session_on_node(node, session_path, api_id, api_hash)
    checked_at = datetime.now(timezone.utc)
    ca = acc.get("created_at")
    created_at = ca.strftime("%Y-%m-%d %H:%M") if hasattr(ca, "strftime") and ca else (str(ca) if ca else None)
    report = _format_status_report(
        phone=acc["phone"],
        is_active=is_active,
        checked_at=checked_at,
        node_name=acc.get("node_name", "—"),
        created_at=created_at,
        error=error,
    )
    try:
        await context.bot.send_message(chat_id=channel_id, text=report)
        await q.edit_message_text("✅ گزارش وضعیت به کانال ارسال شد.")
    except Exception as e:
        log_exception(logger, "Send status to channel failed", e)
        await q.edit_message_text(f"❌ خطا در ارسال به کانال: {str(e)[:80]}")
