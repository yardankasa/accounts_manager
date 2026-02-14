"""Entry point: init DB, bootstrap admins, run bot."""
import asyncio
import logging
import sys

# Ensure project root (parent of src) is on path for "core" and "bot"
if __name__ == "__main__":
    from pathlib import Path
    _src = Path(__file__).resolve().parent
    if str(_src) not in sys.path:
        sys.path.insert(0, str(_src))

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from core.config import BOT_TOKEN, SESSION_DIR
from core import db
from bot.logging_utils import setup_logging
from bot.handlers_admin import cmd_admin, main_menu_back
from bot.handlers_login import login_conversation_handler
from bot.handlers_accounts import accounts_list, account_delete_callback
from bot.handlers_nodes import (
    nodes_list,
    node_manage_callback,
    node_delete_confirm_callback,
    node_add_conversation_handler,
)

logger = logging.getLogger(__name__)


def main() -> None:
    setup_logging()
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set in .env")
        sys.exit(1)

    async def post_init(app: Application) -> None:
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        await db.init_pool()
        await db.bootstrap_admins_from_env()
        logger.info("DB and admins ready")

    async def post_shutdown(app: Application) -> None:
        await db.close_pool()
        logger.info("DB pool closed")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(MessageHandler(filters.Regex("^(بازگشت / انصراف|بازگشت|انصراف)$"), main_menu_back))
    app.add_handler(MessageHandler(filters.Regex("^مدیریت نودها$"), nodes_list))
    app.add_handler(MessageHandler(filters.Regex("^لیست اکانت‌ها$"), accounts_list))
    app.add_handler(login_conversation_handler())
    app.add_handler(node_add_conversation_handler())
    app.add_handler(CallbackQueryHandler(node_manage_callback, pattern="^nodemgr_[0-9]+$"))
    app.add_handler(CallbackQueryHandler(node_delete_confirm_callback, pattern="^nodedel_"))
    app.add_handler(CallbackQueryHandler(account_delete_callback, pattern="^delacc_"))

    logger.info("Bot starting (polling)")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
