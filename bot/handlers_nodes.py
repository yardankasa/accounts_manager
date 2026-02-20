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
from .conversation_utils import handle_main_menu_trigger, dispatch_main_menu_action
from .keyboards import node_manage_inline, node_delete_confirm_inline, node_delete_final_inline, node_main_no_delete_inline, main_admin_keyboard, back_keyboard, inline_keyboard_clear, BACK_TO_MENU
from .messages import (
    MSG_NODES_LIST,
    MSG_NODE_DELETED,
    MSG_NODE_ADDED,
    MSG_DELETE_NODE_CONFIRM,
    MSG_DELETE_NODE_FINAL,
    MSG_CANCELLED,
    MSG_ERROR_GENERIC,
    MSG_ADMIN_PANEL,
    MSG_BACK_HINT,
    MSG_MAIN_NODE_NO_DELETE,
    fa_num,
)
from .logging_utils import log_exception

logger = logging.getLogger(__name__)

# Add node conversation states
ADD_NODE_NAME, ADD_NODE_HOST, ADD_NODE_PORT, ADD_NODE_USER, ADD_NODE_AUTH = range(5)


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
        ip_display = "سرور اصلی" if n.get("is_main") else (n.get("ssh_host") or "—")
        lines.append(f"• {name} │ {ip_display}: {status} – امروز {fa_num(rem)}/۳ ورود")
    text = MSG_NODES_LIST + "\n\n" + "\n".join(lines)
    kb = node_manage_inline(nodes)
    await update.message.reply_text(text, reply_markup=kb)


async def add_node_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_admin(update, context):
        return ConversationHandler.END
    q = update.callback_query
    await q.answer()
    context.user_data["_add_node"] = {}
    await q.edit_message_text("نام نود را وارد کنید:", reply_markup=inline_keyboard_clear)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=MSG_BACK_HINT, reply_markup=back_keyboard())
    return ADD_NODE_NAME


async def node_manage_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_admin(update, context):
        return
    q = update.callback_query
    if not q.data or q.data == "nodemgr_add":
        if q.data:
            await q.answer()
        return
    # Health check: run check on all nodes and report
    if q.data == "nodemgr_healthcheck":
        await q.answer("در حال بررسی...")
        nodes = await db.list_nodes()
        lines = ["🔍 گزارش سلامت نودها:\n"]
        for n in nodes:
            name = n.get("name", f"نود {n['id']}")
            if n.get("is_main"):
                from core.config import SESSION_DIR
                try:
                    SESSION_DIR.mkdir(parents=True, exist_ok=True)
                    lines.append(f"✅ {name} (سرور اصلی): آنلاین")
                except Exception:
                    lines.append(f"❌ {name} (سرور اصلی): خطا")
            else:
                ok, msg = await check_node_connection(n)
                status = "آنلاین" if ok else f"آفلاین ({msg[:40]})"
                icon = "✅" if ok else "❌"
                lines.append(f"{icon} {name}: {status}")
        text = "\n".join(lines)
        await q.edit_message_text(text, reply_markup=inline_keyboard_clear)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=MSG_ADMIN_PANEL,
            reply_markup=main_admin_keyboard(),
        )
        return
    await q.answer()
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
        ip_display = "سرور اصلی" if node.get("is_main") else (node.get("ssh_host") or "—")
        text = f"نود: {node['name']}\nآی‌پی/میز: {ip_display}\nوضعیت: {status}\nامروز: {fa_num(rem)}/۳ ورود\nتعداد اکانت: {fa_num(acc_count)}"
        if node.get("is_main"):
            text += "\n\n" + MSG_MAIN_NODE_NO_DELETE
            kb = node_main_no_delete_inline()
        else:
            text += "\n\n" + MSG_DELETE_NODE_CONFIRM
            kb = node_delete_confirm_inline(node_id)
        await q.edit_message_text(text, reply_markup=kb)
        return


async def node_delete_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_admin(update, context):
        return
    q = update.callback_query
    await q.answer()
    chat_id = update.effective_chat.id
    if q.data == "nodedel_no":
        await q.edit_message_text(MSG_CANCELLED, reply_markup=inline_keyboard_clear)
        await context.bot.send_message(chat_id=chat_id, text=MSG_ADMIN_PANEL, reply_markup=main_admin_keyboard())
        return
    # Step 1: nodedel_yes_{id} -> show second (final) confirmation
    if q.data and q.data.startswith("nodedel_yes_"):
        try:
            node_id = int(q.data.split("_")[2])
        except (IndexError, ValueError):
            return
        node = await db.get_node(node_id)
        if node and node.get("is_main"):
            await q.edit_message_text(MSG_MAIN_NODE_NO_DELETE, reply_markup=inline_keyboard_clear)
            await context.bot.send_message(chat_id=chat_id, text=MSG_ADMIN_PANEL, reply_markup=main_admin_keyboard())
            return
        text = MSG_DELETE_NODE_FINAL
        await q.edit_message_text(text, reply_markup=node_delete_final_inline(node_id))
        return
    # Step 2: nodedel_final_{id} -> actually delete
    if q.data and q.data.startswith("nodedel_final_"):
        try:
            node_id = int(q.data.split("_")[2])
        except (IndexError, ValueError):
            return
        node = await db.get_node(node_id)
        if node and node.get("is_main"):
            await q.edit_message_text(MSG_MAIN_NODE_NO_DELETE, reply_markup=inline_keyboard_clear)
            await context.bot.send_message(chat_id=chat_id, text=MSG_ADMIN_PANEL, reply_markup=main_admin_keyboard())
            return
        try:
            await db.delete_node(node_id)
            await q.edit_message_text(MSG_NODE_DELETED, reply_markup=inline_keyboard_clear)
            await context.bot.send_message(chat_id=chat_id, text=MSG_ADMIN_PANEL, reply_markup=main_admin_keyboard())
        except Exception as e:
            log_exception(logger, "Delete node failed", e)
            await q.edit_message_text(MSG_ERROR_GENERIC, reply_markup=inline_keyboard_clear)
            await context.bot.send_message(chat_id=chat_id, text=MSG_ADMIN_PANEL, reply_markup=main_admin_keyboard())


# --- Add node conversation ---
async def add_node_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("_add_node", None)
    await update.message.reply_text(MSG_CANCELLED, reply_markup=main_admin_keyboard())
    return ConversationHandler.END


async def add_node_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_admin(update, context):
        return ConversationHandler.END
    handled, action = await handle_main_menu_trigger(update, context, "add_node")
    if handled and action:
        await dispatch_main_menu_action(update, context, action)
        return ConversationHandler.END
    text = (update.message.text or "").strip()
    if BACK_TO_MENU in text or "بازگشت به منو" in text or "انصراف" in text or text.strip() == "بازگشت":
        context.user_data.pop("_add_node", None)
        await update.message.reply_text(MSG_CANCELLED, reply_markup=main_admin_keyboard())
        return ConversationHandler.END
    context.user_data["_add_node"]["name"] = text
    await update.message.reply_text("آدرس سرور (host) را وارد کنید:")
    return ADD_NODE_HOST


async def add_node_host(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_admin(update, context):
        return ConversationHandler.END
    handled, action = await handle_main_menu_trigger(update, context, "add_node")
    if handled and action:
        await dispatch_main_menu_action(update, context, action)
        return ConversationHandler.END
    text = (update.message.text or "").strip()
    if BACK_TO_MENU in text or "بازگشت به منو" in text or "انصراف" in text or text.strip() == "بازگشت":
        context.user_data.pop("_add_node", None)
        await update.message.reply_text(MSG_CANCELLED, reply_markup=main_admin_keyboard())
        return ConversationHandler.END
    context.user_data["_add_node"]["host"] = text
    await update.message.reply_text("پورت SSH (عدد، پیش‌فرض ۲۲):")
    return ADD_NODE_PORT


async def add_node_port(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_admin(update, context):
        return ConversationHandler.END
    handled, action = await handle_main_menu_trigger(update, context, "add_node")
    if handled and action:
        await dispatch_main_menu_action(update, context, action)
        return ConversationHandler.END
    text = (update.message.text or "").strip()
    if BACK_TO_MENU in text or "بازگشت به منو" in text or "انصراف" in text or text.strip() == "بازگشت":
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
    handled, action = await handle_main_menu_trigger(update, context, "add_node")
    if handled and action:
        await dispatch_main_menu_action(update, context, action)
        return ConversationHandler.END
    text = (update.message.text or "").strip()
    if BACK_TO_MENU in text or "بازگشت به منو" in text or "انصراف" in text or text.strip() == "بازگشت":
        context.user_data.pop("_add_node", None)
        await update.message.reply_text(MSG_CANCELLED, reply_markup=main_admin_keyboard())
        return ConversationHandler.END
    context.user_data["_add_node"]["user"] = text
    await update.message.reply_text("رمز عبور SSH را وارد کنید:")
    return ADD_NODE_AUTH


async def add_node_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_admin(update, context):
        return ConversationHandler.END
    handled, action = await handle_main_menu_trigger(update, context, "add_node")
    if handled and action:
        await dispatch_main_menu_action(update, context, action)
        return ConversationHandler.END
    text = (update.message.text or "").strip()
    if BACK_TO_MENU in text or "بازگشت به منو" in text or "انصراف" in text or text.strip() == "بازگشت":
        context.user_data.pop("_add_node", None)
        await update.message.reply_text(MSG_CANCELLED, reply_markup=main_admin_keyboard())
        return ConversationHandler.END
    context.user_data["_add_node"]["password"] = text
    data = context.user_data.pop("_add_node", {})
    name = data.get("name", "نود")
    host = data.get("host")
    port = int(data.get("port", 22))
    user = data.get("user")
    password = data.get("password")
    session_base_path = "/opt/rezabots/sessions"
    if not host or not user or not password:
        await update.message.reply_text("اطلاعات ناقص (میز، کاربر و رمز عبور الزامی است). لغو شد.", reply_markup=main_admin_keyboard())
        return ConversationHandler.END
    try:
        node_id = await db.create_node(
            name=name,
            is_main=False,
            session_base_path=session_base_path,
            ssh_host=host,
            ssh_port=port,
            ssh_user=user,
            ssh_key_path=None,
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
        },
        fallbacks=[
            MessageHandler(filters.Regex("^(🏠 بازگشت به منو|بازگشت به منو|بازگشت|انصراف)$"), add_node_cancel),
        ],
        per_message=False,  # Entry is callback; text replies are new messages with different message_id
        per_chat=True,
        per_user=True,
    )
