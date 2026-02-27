"""
Shared logic: when admin sends a main-menu button while inside another conversation,
cancel the current process and start the new one so the admin always sees a response.
"""
import logging
import unicodedata

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

# Zero-width chars and Arabic/Persian normalization (same as filters.py)
_ZERO_WIDTH = frozenset("\u200b\u200c\u200d\ufeff")
_ARABIC_TO_PERSIAN = str.maketrans("\u0643\u064a", "\u06a9\u06cc")


def _normalize(s: str) -> str:
    s = (s or "").strip()
    s = unicodedata.normalize("NFC", s)
    s = "".join(c for c in s if c not in _ZERO_WIDTH)
    s = s.translate(_ARABIC_TO_PERSIAN)
    return s


# Main menu entry texts (raw); normalized form used for matching
_MAIN_MENU_ENTRIES = [
    ("Account Loginer", "login"),
    ("ورود به اکانت", "login"),
    ("📋 لیست اکانت‌ها", "accounts"),
    ("لیست اکانت‌ها", "accounts"),
    ("🖥 مدیریت نودها", "nodes"),
    ("مدیریت نودها", "nodes"),
    ("مدیریت رفتار انسانی", "humantic"),
    ("⭐ Tasks", "tasks"),
    ("Tasks", "tasks"),
]
_NORM_TO_ACTION = {_normalize(raw): action for raw, action in _MAIN_MENU_ENTRIES}


def get_main_menu_action(text: str) -> str | None:
    """Return 'login' | 'accounts' | 'nodes' | 'humantic' | 'tasks' if text is a main menu button, else None."""
    if not text:
        return None
    return _NORM_TO_ACTION.get(_normalize(text))


def cancel_login(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel any in-progress login (task, futures) and clear login-related user_data."""
    task = context.user_data.pop("_login_task", None)
    if task and not task.done():
        task.cancel()
    for k in list(context.user_data.keys()):
        if k.startswith("_"):
            context.user_data.pop(k, None)
    logger.info("Login conversation cancelled (user_data cleared)")


def cancel_add_node(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear add-node conversation state."""
    context.user_data.pop("_add_node", None)
    logger.info("Add-node conversation cancelled")


async def handle_main_menu_trigger(
    update: Update, context: ContextTypes.DEFAULT_TYPE, from_conv: str
) -> tuple[bool, str | None]:
    """
    If the message text is a main menu button, cancel the current conversation and return (True, action).
    from_conv: 'login' or 'add_node'.
    action: 'login' | 'accounts' | 'nodes' | 'humantic' | 'tasks'.
    Otherwise return (False, None).
    """
    if not update.message or not update.message.text:
        return False, None
    action = get_main_menu_action(update.message.text)
    if action is None:
        return False, None
    if from_conv == "login":
        cancel_login(context)
    elif from_conv == "add_node":
        cancel_add_node(context)
    return True, action


MSG_PREVIOUS_CANCELLED = "⏹ فرایند قبلی لغو شد.\n\n"


async def dispatch_main_menu_action(
    update: Update, context: ContextTypes.DEFAULT_TYPE, action: str
):
    """
    Run the handler for the given main menu action. Returns the next conversation state (int or END).
    Uses lazy imports to avoid circular imports.
    """
    chat_id = update.effective_chat.id if update.effective_chat else None
    try:
        if chat_id:
            await context.bot.send_message(chat_id, MSG_PREVIOUS_CANCELLED.strip())
    except Exception:
        pass

    if action == "login":
        from bot.handlers_login import login_entry
        return await login_entry(update, context)
    if action == "accounts":
        from bot.handlers_accounts import accounts_list
        await accounts_list(update, context)
        return ConversationHandler.END
    if action == "nodes":
        from bot.handlers_nodes import nodes_list
        await nodes_list(update, context)
        return ConversationHandler.END
    if action == "humantic":
        from bot.handlers_humantic import humantic_list
        await humantic_list(update, context)
        return ConversationHandler.END
    if action == "tasks":
        from bot.handlers_tasks import tasks_list
        await tasks_list(update, context)
        return ConversationHandler.END
    return ConversationHandler.END
