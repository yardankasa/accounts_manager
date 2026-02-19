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


# Both accepted as "login" entry (keyboard can show either)
LOGIN_ENTRY_TEXTS = (LOGIN_BUTTON, "ورود به اکانت")


class LoginButtonFilter(filters.MessageFilter):
    """Match login entry (e.g. 'Account Loginer' or 'ورود به اکانت') with Unicode normalization so it always works."""

    def filter(self, message):
        if not message or not message.text:
            logger.info("[LOGIN_FILTER] no message or no text -> False")
            return False
        norm_msg = _normalize_for_match(message.text)
        for label in LOGIN_ENTRY_TEXTS:
            if norm_msg == _normalize_for_match(label):
                logger.info("[LOGIN_FILTER] match -> True (text=%r)", message.text[:50])
                return True
        logger.info("[LOGIN_FILTER] mismatch -> False: msg %r (len=%s)", message.text, len(message.text))
        return False


# Single instance for use in handlers
login_button_filter = LoginButtonFilter()


async def ensure_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Return True if user is admin; else reply with access denied and return False."""
    if not update.effective_user:
        logger.info("[ENSURE_ADMIN] no effective_user -> False")
        return False
    user_id = update.effective_user.id
    logger.info("[ENSURE_ADMIN] calling db.is_admin(user_id=%s)", user_id)
    is_admin = await db.is_admin(user_id)
    logger.info("[ENSURE_ADMIN] db.is_admin(%s) -> %s", user_id, is_admin)
    if is_admin:
        return True
    if update.message:
        await update.message.reply_text(MSG_ACCESS_DENIED)
    elif update.callback_query:
        await update.callback_query.answer(MSG_ACCESS_DENIED, show_alert=True)
    return False
