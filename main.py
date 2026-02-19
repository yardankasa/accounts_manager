"""Entry point: init DB, bootstrap admins, run bot."""
import asyncio
import logging
import os
import re
import sys

# Ensure application root (directory containing main.py) is on path for "core" and "bot"
if __name__ == "__main__":
    from pathlib import Path
    _app_root = Path(__file__).resolve().parent
    if str(_app_root) not in sys.path:
        sys.path.insert(0, str(_app_root))

from telegram import Update
from telegram.error import TimedOut, NetworkError
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.request import HTTPXRequest

from core.config import BOT_TOKEN, PROXY_URL, SESSION_DIR, LOGS_DIR
from core import db
from bot.logging_utils import setup_logging
from bot.handlers_admin import cmd_admin, main_menu_back
from bot.handlers_login import login_conversation_handler
from bot.handlers_accounts import (
    accounts_list,
    account_delete_callback,
    account_status_callback,
    im_alive_request_callback,
    im_alive_received,
)
from bot.handlers_nodes import (
    nodes_list,
    node_manage_callback,
    node_delete_confirm_callback,
    node_add_conversation_handler,
)
from bot.handlers_humantic import humantic_list, humantic_callback
from bot.keyboards import HUMANTIC_BUTTON

logger = logging.getLogger(__name__)

# User-facing message when Telegram API is unreachable (timeout/network)
MSG_NETWORK_ERROR = "اتصال به تلگرام برقرار نشد. لطفاً چند لحظه بعد دوباره تلاش کنید."


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors and send a short Persian message on timeout/network errors."""
    exc = context.error
    logger.exception("Update %s caused error: %s", update, exc)
    if isinstance(exc, (TimedOut, NetworkError)):
        try:
            if isinstance(update, Update) and update.effective_chat:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=MSG_NETWORK_ERROR,
                )
        except Exception:
            pass


async def _humantic_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check every 5 min: if humantic enabled and interval passed, run runner and set last_run_at."""
    try:
        from datetime import datetime, timezone
        settings = await db.get_humantic_settings()
        if not settings.get("enabled"):
            return
        interval_hours = float(settings.get("run_interval_hours") or 5)
        last = settings.get("last_run_at")
        now = datetime.now(timezone.utc)
        if last is not None:
            if isinstance(last, str):
                last = datetime.fromisoformat(last.replace("Z", "+00:00"))
            if getattr(last, "tzinfo", None) is None:
                last = last.replace(tzinfo=timezone.utc)
            if (now - last).total_seconds() < interval_hours * 3600:
                return
        await db.update_humantic_settings(last_run_at=now.strftime("%Y-%m-%d %H:%M:%S"))
        from cli_bots.humantic_actions.runner import run_all_accounts
        asyncio.create_task(run_all_accounts(main_node_id_only=True, include_leave=True))
        logger.info("Humantic run started (next in %s h)", interval_hours)
    except Exception as e:
        logger.exception("Humantic job failed: %s", e)


async def _log_incoming_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log every incoming message (group -1, non-blocking) for debugging."""
    if update.message and update.message.text is not None:
        logger.debug(
            "MSG chat_id=%s text=%r len=%s",
            update.effective_chat.id if update.effective_chat else None,
            update.message.text,
            len(update.message.text),
        )


def main() -> None:
    setup_logging()
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set in .env")
        sys.exit(1)
    logger.info("Logs dir: %s", LOGS_DIR.resolve())

    async def post_init(app: Application) -> None:
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        await db.init_pool()
        await db.bootstrap_admins_from_env()
        logger.info("DB and admins ready")
        # Humantic: check every 5 min; run runner when enabled and interval elapsed
        try:
            if app.job_queue:
                app.job_queue.run_repeating(_humantic_job, interval=300, first=60)
                logger.info("Humantic checker scheduled every 5 min")
        except Exception as e:
            logger.warning("Could not schedule humantic job: %s", e)

    async def post_shutdown(app: Application) -> None:
        await db.close_pool()
        logger.info("DB pool closed")

    # Use proxy only from .env (PROXY_URL); ignore HTTP_PROXY/HTTPS_PROXY so invalid schemes like socks:// don't break
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        os.environ.pop(key, None)
    proxy = None
    if PROXY_URL:
        # httpx accepts socks5:// or socks4://, not socks://
        url = PROXY_URL.strip()
        if url.startswith("socks://"):
            url = "socks5://" + url[8:]
        proxy = url
    # Longer timeouts for slow or restricted networks (e.g. servers that need proxy or high latency)
    request = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0, write_timeout=30.0, proxy=proxy)
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .request(request)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    app.add_error_handler(error_handler)

    app.add_handler(CommandHandler("admin", cmd_admin))
    # Log every message (group -1) for debugging
    app.add_handler(
        MessageHandler(filters.TEXT, _log_incoming_message, block=False),
        group=-1,
    )
    # Login: ConversationHandler (entry=Regex like other buttons; states=callback+message steps)
    app.add_handler(login_conversation_handler())
    app.add_handler(MessageHandler(
        filters.Regex("^(🏠 بازگشت به منو|بازگشت به منو|بازگشت / انصراف|بازگشت|انصراف)$"),
        main_menu_back,
    ))
    app.add_handler(MessageHandler(filters.Regex("^(🖥 مدیریت نودها|مدیریت نودها)$"), nodes_list))
    app.add_handler(MessageHandler(filters.Regex("^(📋 لیست اکانت‌ها|لیست اکانت‌ها)$"), accounts_list))
    app.add_handler(MessageHandler(filters.Regex(f"^({re.escape(HUMANTIC_BUTTON)})$"), humantic_list))
    app.add_handler(CallbackQueryHandler(humantic_callback, pattern="^hum_"))
    app.add_handler(node_add_conversation_handler())
    app.add_handler(CallbackQueryHandler(node_manage_callback, pattern="^nodemgr_"))
    app.add_handler(CallbackQueryHandler(node_delete_confirm_callback, pattern="^nodedel_"))
    app.add_handler(CallbackQueryHandler(account_status_callback, pattern="^statusacc_"))
    app.add_handler(CallbackQueryHandler(im_alive_request_callback, pattern="^im_alive_req_"))
    app.add_handler(CallbackQueryHandler(account_delete_callback, pattern="^delacc_"))
    app.add_handler(MessageHandler(filters.Regex("^/im_alive_"), im_alive_received))

    logger.info("Bot starting (polling)")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
