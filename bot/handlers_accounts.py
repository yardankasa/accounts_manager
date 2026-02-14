"""Account list and delete."""
import logging
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler, filters

import core.db as db
from core.node_runner import check_node_connection

from .filters import ensure_admin
from .keyboards import account_list_inline, main_admin_keyboard
from .messages import MSG_ACCOUNTS_LIST, MSG_NO_ACCOUNTS, MSG_ACCOUNT_DELETED, MSG_ERROR_GENERIC
from .logging_utils import log_exception

logger = logging.getLogger(__name__)


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
