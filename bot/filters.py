"""Admin check: use in handlers to restrict access. Login button filter with Unicode normalization."""
import unicodedata

from telegram import Update
from telegram.ext import ContextTypes, filters

import core.db as db
from .keyboards import LOGIN_BUTTON
from .messages import MSG_ACCESS_DENIED


class LoginButtonFilter(filters.MessageFilter):
    """Match 'ورود به اکانت' with Unicode NFC normalization so Telegram NFD or extra chars still match."""

    def filter(self, message):
        if not message or not message.text:
            return False
        text = (message.text or "").strip()
        return unicodedata.normalize("NFC", text) == unicodedata.normalize("NFC", LOGIN_BUTTON)


# Single instance for use in handlers
login_button_filter = LoginButtonFilter()


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
