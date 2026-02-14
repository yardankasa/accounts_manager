"""Node management: list, status, add, delete."""
import logging
from telegram import Update
from telegram.ext import (
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)

import core.db as db
import core.limits as limits
from core.node_runner import check_node_connection

from .filters import ensure_admin
from .keyboards import node_manage_inline, node_delete_confirm_inline, main_admin_keyboard, back_keyboard
from .messages import (
    MSG_NODES_LIST,
    MSG_NODE_DELETED,
    MSG_NODE_ADDED,
    MSG_DELETE_NODE_CONFIRM,
    MSG_CANCELLED,
    MSG_ERROR_GENERIC,
)
from .logging_utils import log_exception

logger = logging.getLogger(__name__)

# Add node conversation states
ADD_NODE_NAME, ADD_NODE_HOST, ADD_NODE_PORT, ADD_NODE_USER, ADD_NODE_AUTH, ADD_NODE_SESSION_PATH = range(6)


async def nodes_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_admin(update, context):
        return
    nodes = await db.list_nodes()
    if not nodes:
        await update.message.reply_text("هیچ نودی ثبت نشده. نود اصلی به‌صورت خودکار ایجاد می‌شود.", reply_markup=main_admin_keyboard())
        return
    lines = []
    for n in nodes:
        rem = await limits.remaining_logins_today(n["id"])
        status = "آنلاین" if n.get("is_main") else "?"
        if not n.get("is_main"):
            ok, _ = await check_node_connection(n)
            status = "آنلاین" if ok else "آفلاین"
        name = n["name"]
        lines.append(f"• {name}: {status} – امروز {rem}/۳ ورود")
    text = MSG_NODES_LIST + "\n\n" + "\n".join(lines)
    kb = node_manage_inline(nodes)
    await update.message.reply_text(text, reply_markup=kb)


async def add_node_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_admin(update, context):
        return ConversationHandler.END
    q = update.callback_query
    await q.answer()
    context.user_data["_add_node"] = {}
    await q.edit_message_text("نام نود را وارد کنید:", reply_markup=back_keyboard())
    return ADD_NODE_NAME


async def node_manage_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_admin(update, context):
        return
    q = update.callback_query
    await q.answer()
    if not q.data or q.data == "nodemgr_add":
        return
    if q.data.startswith("nodemgr_"):
        try:
            node_id = int(q.data.split("_")[1])
        except (IndexError, ValueError):
            return
        node = await db.get_node(node_id)
        if not node:
            await q.edit_message_text("نود یافت نشد.")
            return
        rem = await limits.remaining_logins_today(node_id)
        status = "آنلاین" if node.get("is_main") else "?"
        if not node.get("is_main"):
            ok, _ = await check_node_connection(node)
            status = "آنلاین" if ok else "آفلاین"
        accs = await db.list_accounts(node_id=node_id)
        acc_count = len(accs)
        text = f"نود: {node['name']}\nوضعیت: {status}\nامروز: {rem}/۳ ورود\nتعداد اکانت: {acc_count}"
        kb = node_delete_confirm_inline(node_id)
        await q.edit_message_text(text + "\n\n" + MSG_DELETE_NODE_CONFIRM, reply_markup=kb)
        return


async def node_delete_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_admin(update, context):
        return
    q = update.callback_query
    await q.answer()
    if q.data == "nodedel_no":
        await q.edit_message_text(MSG_CANCELLED, reply_markup=main_admin_keyboard())
        return
    if q.data and q.data.startswith("nodedel_yes_"):
        try:
            node_id = int(q.data.split("_")[2])
        except (IndexError, ValueError):
            return
        try:
            await db.delete_node(node_id)
            await q.edit_message_text(MSG_NODE_DELETED, reply_markup=main_admin_keyboard())
        except Exception as e:
            log_exception(logger, "Delete node failed", e)
            await q.edit_message_text(MSG_ERROR_GENERIC, reply_markup=main_admin_keyboard())


# --- Add node conversation ---
async def add_node_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("_add_node", None)
    await update.message.reply_text(MSG_CANCELLED, reply_markup=main_admin_keyboard())
    return ConversationHandler.END


async def add_node_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_admin(update, context):
        return ConversationHandler.END
    text = (update.message.text or "").strip()
    if "انصراف" in text or "بازگشت" in text:
        context.user_data.pop("_add_node", None)
        await update.message.reply_text(MSG_CANCELLED, reply_markup=main_admin_keyboard())
        return ConversationHandler.END
    context.user_data["_add_node"]["name"] = text
    await update.message.reply_text("آدرس سرور (host) را وارد کنید:")
    return ADD_NODE_HOST


async def add_node_host(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_admin(update, context):
        return ConversationHandler.END
    text = (update.message.text or "").strip()
    if "انصراف" in text or "بازگشت" in text:
        context.user_data.pop("_add_node", None)
        await update.message.reply_text(MSG_CANCELLED, reply_markup=main_admin_keyboard())
        return ConversationHandler.END
    context.user_data["_add_node"]["host"] = text
    await update.message.reply_text("پورت SSH (عدد، پیش‌فرض ۲۲):")
    return ADD_NODE_PORT


async def add_node_port(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_admin(update, context):
        return ConversationHandler.END
    text = (update.message.text or "").strip()
    if "انصراف" in text or "بازگشت" in text:
        context.user_data.pop("_add_node", None)
        await update.message.reply_text(MSG_CANCELLED, reply_markup=main_admin_keyboard())
        return ConversationHandler.END
    try:
        port = int(text) if text else 22
    except ValueError:
        port = 22
    context.user_data["_add_node"]["port"] = port
    await update.message.reply_text("نام کاربری SSH را وارد کنید:")
    return ADD_NODE_USER


async def add_node_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_admin(update, context):
        return ConversationHandler.END
    text = (update.message.text or "").strip()
    if "انصراف" in text or "بازگشت" in text:
        context.user_data.pop("_add_node", None)
        await update.message.reply_text(MSG_CANCELLED, reply_markup=main_admin_keyboard())
        return ConversationHandler.END
    context.user_data["_add_node"]["user"] = text
    await update.message.reply_text("مسیر کلید SSH (فایل) یا رمز SSH را وارد کنید. برای کلید مسیر کامل بدهید:")
    return ADD_NODE_AUTH


async def add_node_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_admin(update, context):
        return ConversationHandler.END
    text = (update.message.text or "").strip()
    if "انصراف" in text or "بازگشت" in text:
        context.user_data.pop("_add_node", None)
        await update.message.reply_text(MSG_CANCELLED, reply_markup=main_admin_keyboard())
        return ConversationHandler.END
    if text.startswith("/") or "." in text:
        context.user_data["_add_node"]["key_path"] = text
        context.user_data["_add_node"]["password"] = None
    else:
        context.user_data["_add_node"]["password"] = text
        context.user_data["_add_node"]["key_path"] = None
    await update.message.reply_text("مسیر پوشهٔ session روی سرور نود (مثال: /opt/rezabots/data/session):")
    return ADD_NODE_SESSION_PATH


async def add_node_session_path(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_admin(update, context):
        return ConversationHandler.END
    text = (update.message.text or "").strip()
    if "انصراف" in text or "بازگشت" in text:
        context.user_data.pop("_add_node", None)
        await update.message.reply_text(MSG_CANCELLED, reply_markup=main_admin_keyboard())
        return ConversationHandler.END
    data = context.user_data.pop("_add_node", {})
    name = data.get("name", "نود")
    host = data.get("host")
    port = int(data.get("port", 22))
    user = data.get("user")
    key_path = data.get("key_path")
    password = data.get("password")
    session_base_path = text or "/opt/rezabots/data/session"
    if not host or not user:
        await update.message.reply_text("اطلاعات ناقص. لغو شد.", reply_markup=main_admin_keyboard())
        return ConversationHandler.END
    try:
        node_id = await db.create_node(
            name=name,
            is_main=False,
            session_base_path=session_base_path,
            ssh_host=host,
            ssh_port=port,
            ssh_user=user,
            ssh_key_path=key_path,
            ssh_password=password,
        )
        # Verify connection
        node = await db.get_node(node_id)
        ok, msg = await check_node_connection(node) if node else (False, "نود یافت نشد")
        if ok:
            await update.message.reply_text(MSG_NODE_ADDED, reply_markup=main_admin_keyboard())
        else:
            await update.message.reply_text(f"نود ذخیره شد ولی اتصال برقرار نشد: {msg}", reply_markup=main_admin_keyboard())
    except Exception as e:
        log_exception(logger, "Add node failed", e)
        await update.message.reply_text(MSG_ERROR_GENERIC, reply_markup=main_admin_keyboard())
    return ConversationHandler.END


def node_add_conversation_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(add_node_entry, pattern="^nodemgr_add$")],
        states={
            ADD_NODE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_node_name)],
            ADD_NODE_HOST: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_node_host)],
            ADD_NODE_PORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_node_port)],
            ADD_NODE_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_node_user)],
            ADD_NODE_AUTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_node_auth)],
            ADD_NODE_SESSION_PATH: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_node_session_path)],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^(بازگشت|انصراف)$"), add_node_cancel),
        ],
        per_chat=True,
        per_user=True,
    )
