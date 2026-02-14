"""Admin check: use in handlers to restrict access."""
from telegram import Update
from telegram.ext import ContextTypes

import core.db as db
from .messages import MSG_ACCESS_DENIED


async def ensure_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Return True if user is admin; else reply with access denied and return False."""
    if not update.effective_user:
        return False
    if await db.is_admin(update.effective_user.id):
        return True
    if update.message:
        await update.message.reply_text(MSG_ACCESS_DENIED)
    elif update.callback_query:
        await update.callback_query.answer(MSG_ACCESS_DENIED, show_alert=True)
    return False
