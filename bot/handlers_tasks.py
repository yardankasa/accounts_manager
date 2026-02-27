"""Admin panel: Tasks (Stars bots) – enable/disable and manual run."""
import asyncio
import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

import core.db as db
from .filters import ensure_admin
from .keyboards import main_admin_keyboard, tasks_manage_inline
from .messages import MSG_TASKS_PANEL, MSG_TASKS_ON, MSG_TASKS_OFF, MSG_TASKS_RUN_NOW

logger = logging.getLogger(__name__)


def _format_tasks_panel(settings: dict) -> str:
    enabled = bool(settings.get("enabled", False))
    status = "روشن ✅" if enabled else "خاموش ❌"
    interval = int(settings.get("run_interval_minutes") or 30)
    last_run = settings.get("last_run_at")
    if isinstance(last_run, datetime):
        last_run_str = last_run.strftime("%Y-%m-%d %H:%M")
    elif last_run:
        last_run_str = str(last_run)
    else:
        last_run_str = "—"
    return MSG_TASKS_PANEL.format(
        status=status,
        interval=interval,
        last_run=last_run_str,
    )


async def tasks_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show Tasks settings and inline keyboard (entry: Tasks button)."""
    if not await ensure_admin(update, context):
        return
    settings = await db.get_tasks_settings()
    text = _format_tasks_panel(settings)
    await update.message.reply_text(
        text,
        reply_markup=tasks_manage_inline(settings),
    )


async def tasks_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline callbacks: tasks_on/off and manual run."""
    if not await ensure_admin(update, context):
        return
    q = update.callback_query
    await q.answer()
    if not q.data or not q.data.startswith("tasks_"):
        return

    data = q.data
    settings = await db.get_tasks_settings()

    if data == "tasks_on":
        await db.update_tasks_settings(enabled=True)
        settings = await db.get_tasks_settings()
        await q.edit_message_text(
            MSG_TASKS_ON + "\n\n" + _format_tasks_panel(settings),
            reply_markup=tasks_manage_inline(settings),
        )
    elif data == "tasks_off":
        await db.update_tasks_settings(enabled=False)
        settings = await db.get_tasks_settings()
        await q.edit_message_text(
            MSG_TASKS_OFF + "\n\n" + _format_tasks_panel(settings),
            reply_markup=tasks_manage_inline(settings),
        )
    elif data == "tasks_run_now":
        # Fire-and-forget manual run; scheduler will also run based on interval
        from cli_bots.tasks import run_tasks_for_all_accounts

        asyncio.create_task(run_tasks_for_all_accounts())
        await q.edit_message_text(
            MSG_TASKS_RUN_NOW + "\n\n" + _format_tasks_panel(settings),
            reply_markup=tasks_manage_inline(settings),
        )
    else:
        await q.edit_message_text(
            _format_tasks_panel(settings),
            reply_markup=tasks_manage_inline(settings),
        )

