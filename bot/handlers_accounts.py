"""Account list, delete, status check, and im_alive request."""
import logging
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler, filters

import core.db as db
from core.config import BOT_USERNAME
from core.node_runner import (
    check_node_connection,
    check_session_on_node,
    send_messages_to_bot_on_node,
)

from .filters import ensure_admin
from .keyboards import account_list_inline, main_admin_keyboard
from .messages import MSG_ACCOUNTS_LIST, MSG_NO_ACCOUNTS, MSG_ACCOUNT_DELETED, MSG_ERROR_GENERIC
from .logging_utils import log_exception

# Button text for "request send message to bot"
MSG_IM_ALIVE_BTN = "👓 درخواست ارسال پیام به ربات"

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
    """Format account status report (session active or not + info)."""
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
    """Check account session status and show result to user."""
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
    # Add "درخواست ارسال پیام به ربات" button only when session is active
    reply_markup = None
    if is_active and BOT_USERNAME:
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(MSG_IM_ALIVE_BTN, callback_data=f"im_alive_req_{account_id}")],
        ])
    await q.edit_message_text(report, reply_markup=reply_markup)


async def im_alive_request_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Account sends /start and /im_alive_$phone to the bot."""
    if not await ensure_admin(update, context):
        return
    q = update.callback_query
    await q.answer("در حال ارسال پیام...")
    if not q.data or not q.data.startswith("im_alive_req_"):
        return
    try:
        account_id = int(q.data.split("_")[3])
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
        await q.edit_message_text("API_ID و API_HASH ذخیره نشده.")
        return
    if not BOT_USERNAME:
        await q.edit_message_text("❌ BOT_USERNAME در .env تنظیم نشده.")
        return
    node = await db.get_node(acc["node_id"])
    if not node:
        await q.edit_message_text("نود یافت نشد.")
        return
    phone = "".join(c for c in acc["phone"] if c.isdigit())
    messages = ["/start", f"/im_alive_{phone}"]
    ok, err = await send_messages_to_bot_on_node(
        node, acc["session_path"], api_id, api_hash,
        BOT_USERNAME, messages,
    )
    if ok:
        await q.edit_message_text(
            "✅ پیام ارسال شد. اکانت /start و /im_alive را به ربات فرستاد.\n"
            "منتظر پاسخ ربات باشید."
        )
    else:
        await q.edit_message_text(f"❌ خطا در ارسال: {err}")


async def im_alive_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """When account sends /im_alive_$phone to bot, notify admins."""
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    if not text.startswith("/im_alive_"):
        return
    try:
        phone = text.replace("/im_alive_", "", 1).strip()
        if not phone:
            return
    except Exception:
        return
    # Notify all admins
    admin_ids = await db.list_admin_ids()
    masked = _mask_phone(phone)
    msg = (
        f"✅ ربات در حال انجام کار است.\n"
        f"📱 اکانت {masked} پیام im_alive ارسال کرد.\n"
        f"📡 نشست فعال و آمادهٔ سرویس است."
    )
    for aid in admin_ids:
        try:
            await context.bot.send_message(chat_id=aid, text=msg)
        except Exception as e:
            logger.warning("Notify admin %s failed: %s", aid, e)
