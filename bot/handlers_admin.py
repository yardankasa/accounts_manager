"""Admin panel and main menu handlers."""
import logging
from telegram import Update
from telegram.ext import ContextTypes

from .filters import ensure_admin
from .keyboards import main_admin_keyboard, cancel_keyboard
from .messages import MSG_ACCESS_DENIED, MSG_ADMIN_PANEL, MSG_CANCELLED

logger = logging.getLogger(__name__)


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Entry: /admin - show panel only for admins."""
    if not update.effective_user:
        return
    if not await ensure_admin(update, context):
        # ensure_admin already replied with MSG_ACCESS_DENIED when message exists
        if not update.message:
            return
        # For /admin we check and reply inside ensure_admin; if False we already sent access denied
        return
    await update.message.reply_text(
        MSG_ADMIN_PANEL,
        reply_markup=main_admin_keyboard(),
    )


async def main_menu_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """بازگشت / انصراف: remove keyboard and show short message."""
    if not await ensure_admin(update, context):
        return
    await update.message.reply_text(MSG_CANCELLED, reply_markup=cancel_keyboard())
