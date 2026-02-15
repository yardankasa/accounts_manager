"""Login flow: ConversationHandler for node -> phone -> code -> 2FA."""
import asyncio
import logging

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    filters,
)

import core.db as db
import core.limits as limits
import core.node_runner as node_runner
from core.config import SESSION_DIR

from .filters import ensure_admin, login_button_filter
from .keyboards import LOGIN_BUTTON, node_choice_inline, back_keyboard, main_admin_keyboard, inline_keyboard_clear, BACK_TO_MENU
from .messages import (
    MSG_CHOOSE_NODE,
    MSG_NO_NODE_CAPACITY,
    MSG_ENTER_API_ID,
    MSG_ENTER_API_HASH,
    MSG_INVALID_API_ID,
    MSG_INVALID_API_HASH,
    MSG_ENTER_PHONE,
    MSG_INVALID_PHONE,
    MSG_ENTER_CODE,
    MSG_WRONG_CODE,
    MSG_ENTER_2FA,
    MSG_LOGIN_SUCCESS,
    MSG_LOGIN_CANCELLED,
    MSG_MAX_WRONG_CODE,
    MSG_BACK_HINT,
)
from .logging_utils import log_exception

logger = logging.getLogger(__name__)



CHOOSE_NODE, ENTER_API_ID, ENTER_API_HASH, ENTER_PHONE, ENTER_CODE = range(5)
MAX_WRONG_CODE_ATTEMPTS = 2


def _normalize_phone(text: str) -> str | None:
    """Normalize to digits only. Iranian 09xxxxxxxxx -> 98..., rest as international (e.g. 254...)."""
    s = "".join(c for c in text if c.isdigit())
    if not s or len(s) < 10:
        return None
    # Iranian: 09xxxxxxxx or 9xxxxxxxx (10 digits) -> 98xxxxxxxxx
    if len(s) == 10 and s.startswith("0") and s[1] == "9":
        return "98" + s[1:]
    if len(s) == 10 and s.startswith("9"):
        return "98" + s
    # Already has country code (e.g. 98..., 254..., 1...) or 11+ digits
    if s.startswith("98") and len(s) >= 11:
        return s
    # Other international: keep as-is (e.g. 254796276463)
    return s


# --- Entry: show node selection
async def login_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("[LOGIN_ENTRY] called text=%r", getattr(update.message, "text", None))
    if not update.message or not update.message.text:
        logger.info("[LOGIN_ENTRY] no message/text -> END")
        return ConversationHandler.END
    logger.info("[LOGIN_ENTRY] calling ensure_admin")
    if not await ensure_admin(update, context):
        logger.info("[LOGIN_ENTRY] ensure_admin -> False, END")
        return ConversationHandler.END
    try:
        context.user_data["_chat_id"] = update.effective_chat.id
        context.user_data["_bot"] = context.bot
        logger.info("[LOGIN_ENTRY] calling db.list_nodes()")
        nodes = await db.list_nodes()
        logger.info("[LOGIN_ENTRY] db.list_nodes() -> %s nodes", len(nodes))
        nodes_with_remaining = []
        for n in nodes:
            logger.info("[LOGIN_ENTRY] calling limits.remaining_logins_today(node_id=%s)", n["id"])
            rem = await limits.remaining_logins_today(n["id"])
            logger.info("[LOGIN_ENTRY] limits.remaining_logins_today(%s) -> %s", n["id"], rem)
            nodes_with_remaining.append((n["id"], n["name"], rem))
        if not any(r > 0 for _, _, r in nodes_with_remaining):
            logger.info("[LOGIN_ENTRY] no node capacity, sending MSG_NO_NODE_CAPACITY")
            await update.message.reply_text(MSG_NO_NODE_CAPACITY, reply_markup=main_admin_keyboard())
            return ConversationHandler.END
        kb = node_choice_inline(nodes_with_remaining)
        logger.info("[LOGIN_ENTRY] sending MSG_CHOOSE_NODE")
        await update.message.reply_text(MSG_CHOOSE_NODE, reply_markup=kb)
        logger.info("[LOGIN_ENTRY] -> CHOOSE_NODE")
        return CHOOSE_NODE
    except Exception as e:
        log_exception(logger, "login_entry failed", e)
        try:
            await update.message.reply_text(
                "❌ خطا در نمایش نودها. لطفاً دوباره تلاش کنید.",
                reply_markup=main_admin_keyboard(),
            )
        except Exception:
            pass
        return ConversationHandler.END


# --- Choose node (inline callback)
async def login_choose_node_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("[LOGIN_CHOOSE_NODE] callback data=%r", getattr(update.callback_query, "data", None))
    if not await ensure_admin(update, context):
        logger.info("[LOGIN_CHOOSE_NODE] ensure_admin -> False, END")
        return ConversationHandler.END
    q = update.callback_query
    await q.answer()
    if not q.data or not q.data.startswith("node_"):
        logger.info("[LOGIN_CHOOSE_NODE] invalid data -> CHOOSE_NODE")
        return CHOOSE_NODE
    node_id = int(q.data.split("_")[1])
    logger.info("[LOGIN_CHOOSE_NODE] calling limits.can_login_on_node(node_id=%s)", node_id)
    ok, reason = await limits.can_login_on_node(node_id)
    logger.info("[LOGIN_CHOOSE_NODE] limits.can_login_on_node(%s) -> ok=%s reason=%r", node_id, ok, reason)
    if not ok:
        await q.edit_message_text(reason)
        return ConversationHandler.END
    logger.info("[LOGIN_CHOOSE_NODE] calling db.get_node(node_id=%s)", node_id)
    node = await db.get_node(node_id)
    logger.info("[LOGIN_CHOOSE_NODE] db.get_node(%s) -> %s", node_id, "found" if node else "None")
    if not node:
        await q.edit_message_text("نود یافت نشد.")
        return ConversationHandler.END
    logger.info("[LOGIN_CHOOSE_NODE] calling node_runner.check_node_connection")
    ok, msg = await node_runner.check_node_connection(node)
    logger.info("[LOGIN_CHOOSE_NODE] node_runner.check_node_connection -> ok=%s msg=%r", ok, msg)
    if not ok:
        await q.edit_message_text(msg)
        return CHOOSE_NODE
    context.user_data["_node_id"] = node_id
    context.user_data["_node"] = node
    logger.info("[LOGIN_CHOOSE_NODE] sending MSG_ENTER_API_ID + MSG_BACK_HINT")
    await q.edit_message_text(MSG_ENTER_API_ID, reply_markup=inline_keyboard_clear)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=MSG_BACK_HINT, reply_markup=back_keyboard())
    logger.info("[LOGIN_CHOOSE_NODE] -> ENTER_API_ID")
    return ENTER_API_ID


# --- Enter API_ID
async def login_enter_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("[LOGIN_API_ID] text=%r", (update.message.text or "").strip())
    if not await ensure_admin(update, context):
        return ConversationHandler.END
    text = (update.message.text or "").strip()
    if BACK_TO_MENU in text or "بازگشت به منو" in text or "انصراف" in text or text.strip() == "بازگشت":
        await update.message.reply_text(MSG_LOGIN_CANCELLED, reply_markup=main_admin_keyboard())
        return ConversationHandler.END
    try:
        api_id = int(text)
    except ValueError:
        await update.message.reply_text(MSG_INVALID_API_ID)
        return ENTER_API_ID
    context.user_data["_api_id"] = api_id
    logger.info("[LOGIN_API_ID] -> ENTER_API_HASH")
    await update.message.reply_text(MSG_ENTER_API_HASH)
    return ENTER_API_HASH


# --- Enter API_HASH
async def login_enter_api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("[LOGIN_API_HASH] text len=%s", len((update.message.text or "").strip()))
    if not await ensure_admin(update, context):
        return ConversationHandler.END
    text = (update.message.text or "").strip()
    if BACK_TO_MENU in text or "بازگشت به منو" in text or "انصراف" in text or text.strip() == "بازگشت":
        await update.message.reply_text(MSG_LOGIN_CANCELLED, reply_markup=main_admin_keyboard())
        return ConversationHandler.END
    if not text or len(text) < 10:
        await update.message.reply_text(MSG_INVALID_API_HASH)
        return ENTER_API_HASH
    context.user_data["_api_hash"] = text
    logger.info("[LOGIN_API_HASH] -> ENTER_PHONE")
    await update.message.reply_text(MSG_ENTER_PHONE, reply_markup=back_keyboard())
    return ENTER_PHONE


# --- Enter phone
async def login_enter_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("[LOGIN_PHONE] text=%r", (update.message.text or "").strip()[:20])
    if not await ensure_admin(update, context):
        return ConversationHandler.END
    text = (update.message.text or "").strip()
    if "انصراف" in text or "بازگشت" in text:
        await update.message.reply_text(MSG_LOGIN_CANCELLED, reply_markup=main_admin_keyboard())
        return ConversationHandler.END
    phone = _normalize_phone(text)
    if not phone:
        await update.message.reply_text(MSG_INVALID_PHONE)
        return ENTER_PHONE
    node_id = context.user_data["_node_id"]
    node = context.user_data["_node"]
    session_base = node["session_base_path"] if node.get("session_base_path") else str(SESSION_DIR)
    if node.get("is_main"):
        session_base = str(SESSION_DIR)
    context.user_data["_phone"] = phone
    context.user_data["_session_base"] = session_base
    context.user_data["_wrong_code_count"] = 0

    chat_id = context.user_data["_chat_id"]
    bot = context.user_data["_bot"]

    async def code_cb():
        logger.info("[LOGIN_SERVICE] code_callback requested")
        fut = context.user_data.get("_code_future")
        if fut is None:
            fut = asyncio.get_event_loop().create_future()
            context.user_data["_code_future"] = fut
        return await fut

    async def pwd_cb():
        logger.info("[LOGIN_SERVICE] password_callback requested")
        await bot.send_message(chat_id, MSG_ENTER_2FA)
        fut = context.user_data.get("_password_future")
        if fut is None:
            fut = asyncio.get_event_loop().create_future()
            context.user_data["_password_future"] = fut
        return await fut

    api_id = context.user_data["_api_id"]
    api_hash = context.user_data["_api_hash"]

    async def run_and_finish():
        try:
            logger.info("[LOGIN_SERVICE] calling node_runner.run_login_on_node(node_id=%s, phone=%s)", node_id, phone[:6])
            success, msg, session_path = await node_runner.run_login_on_node(
                node_id=node_id,
                phone=phone,
                session_base_path=session_base,
                api_id=api_id,
                api_hash=api_hash,
                code_callback=code_cb,
                password_callback=pwd_cb,
            )
            logger.info("[LOGIN_SERVICE] node_runner.run_login_on_node -> success=%s session_path=%s", success, session_path)
            if success and session_path:
                logger.info("[LOGIN_SERVICE] calling db.record_login_event(%s)", node_id)
                await db.record_login_event(node_id)
                logger.info("[LOGIN_SERVICE] calling db.create_account(node_id=%s, phone=%s)", node_id, phone[:6])
                await db.create_account(node_id, phone, session_path)
            await bot.send_message(chat_id, msg)
        except Exception as e:
            log_exception(logger, "Login task failed", e)
            await bot.send_message(chat_id, "خطا در ورود: " + str(e)[:150])
        finally:
            context.user_data["_login_done"] = True
            for k in ("_code_future", "_password_future", "_login_task"):
                context.user_data.pop(k, None)

    task = asyncio.create_task(run_and_finish())
    context.user_data["_login_task"] = task
    context.user_data["_code_future"] = asyncio.get_event_loop().create_future()
    logger.info("[LOGIN_PHONE] sending MSG_ENTER_CODE -> ENTER_CODE")
    await update.message.reply_text(MSG_ENTER_CODE)
    return ENTER_CODE


# --- Enter code (and optionally 2FA)
async def login_enter_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("[LOGIN_CODE] text len=%s", len((update.message.text or "").strip()))
    if not await ensure_admin(update, context):
        return ConversationHandler.END
    text = (update.message.text or "").strip()
    if BACK_TO_MENU in text or "بازگشت به منو" in text or "انصراف" in text or text.strip() == "بازگشت":
        context.user_data.pop("_login_task", None)
        context.user_data.pop("_code_future", None)
        context.user_data.pop("_password_future", None)
        await update.message.reply_text(MSG_LOGIN_CANCELLED, reply_markup=main_admin_keyboard())
        return ConversationHandler.END
    if context.user_data.get("_login_done"):
        for k in list(context.user_data.keys()):
            if k.startswith("_"):
                context.user_data.pop(k, None)
        return ConversationHandler.END
    password_future = context.user_data.get("_password_future")
    code_future = context.user_data.get("_code_future")
    if password_future is not None and not password_future.done():
        logger.info("[LOGIN_CODE] setting password_future result")
        password_future.set_result(text)
        return ENTER_CODE
    if code_future is not None and not code_future.done():
        logger.info("[LOGIN_CODE] setting code_future result")
        code_future.set_result(text)
    return ENTER_CODE


async def login_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("[LOGIN_CANCEL] called")
    if not await ensure_admin(update, context):
        return ConversationHandler.END
    task = context.user_data.pop("_login_task", None)
    if task and not task.done():
        task.cancel()
    for k in list(context.user_data.keys()):
        if k.startswith("_"):
            context.user_data.pop(k, None)
    await update.message.reply_text(MSG_LOGIN_CANCELLED, reply_markup=main_admin_keyboard())
    return ConversationHandler.END


def login_conversation_handler():
    # Use login_button_filter so the login button label matches with Unicode normalization.
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & login_button_filter, login_entry),
        ],
        states={
            CHOOSE_NODE: [
                CallbackQueryHandler(login_choose_node_callback, pattern="^node_"),
            ],
            ENTER_API_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, login_enter_api_id),
            ],
            ENTER_API_HASH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, login_enter_api_hash),
            ],
            ENTER_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, login_enter_phone),
            ],
            ENTER_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, login_enter_code),
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^(🏠 بازگشت به منو|بازگشت به منو|بازگشت|انصراف|بازگشت / انصراف)$"), login_cancel),
            CommandHandler("cancel", login_cancel),
        ],
        per_message=True,
        per_chat=True,
        per_user=True,
    )
