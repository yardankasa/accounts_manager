"""Admin check: use in handlers to restrict access. Login button filter with Unicode normalization."""
import logging
import unicodedata

from telegram import Update
from telegram.ext import ContextTypes, filters

import core.db as db
from .keyboards import LOGIN_BUTTON
from .messages import MSG_ACCESS_DENIED

logger = logging.getLogger(__name__)

# Zero-width chars Telegram may insert in Persian keyboard button text (ZWNJ, ZWSP, ZWJ, BOM)
_ZERO_WIDTH = frozenset("\u200b\u200c\u200d\ufeff")

# Arabic/Persian variants that look the same but have different code points (normalize to Persian form for matching)
_ARABIC_TO_PERSIAN = str.maketrans("\u0643\u064a", "\u06a9\u06cc")  # ك->ک, ي->ی


def _normalize_for_match(s: str) -> str:
    """NFC normalize, remove zero-width chars, and unify Arabic/Persian variants so button text matches."""
    s = (s or "").strip()
    s = unicodedata.normalize("NFC", s)
    s = "".join(c for c in s if c not in _ZERO_WIDTH)
    s = s.translate(_ARABIC_TO_PERSIAN)
    return s


class LoginButtonFilter(filters.MessageFilter):
    """Match the login button text (e.g. 'Account Loginer') with Unicode normalization."""

    def filter(self, message):
        if not message or not message.text:
            return False
        norm_msg = _normalize_for_match(message.text)
        norm_btn = _normalize_for_match(LOGIN_BUTTON)
        if norm_msg != norm_btn:
            logger.debug(
                "Login button mismatch: msg %r (len=%s, repr=%s) vs btn %r (len=%s)",
                message.text, len(message.text), [hex(ord(c)) for c in message.text],
                LOGIN_BUTTON, len(LOGIN_BUTTON),
            )
            return False
        return True


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
