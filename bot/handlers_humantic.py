"""Admin panel: مدیریت رفتار انسانی — on/off, schedule, leave-after."""
import logging
from telegram import Update
from telegram.ext import ContextTypes

import core.db as db
from .filters import ensure_admin
from .keyboards import main_admin_keyboard, humantic_manage_inline
from .messages import (
    MSG_HUMANTIC_PANEL,
    MSG_HUMANTIC_ON,
    MSG_HUMANTIC_OFF,
    MSG_HUMANTIC_INTERVAL,
    MSG_HUMANTIC_LEAVE,
)

logger = logging.getLogger(__name__)


def _format_panel(settings: dict) -> str:
    status = "روشن ✅" if settings.get("enabled") else "خاموش ❌"
    interval = settings.get("run_interval_hours", 5)
    leave_min = settings.get("leave_after_min_hours", 2)
    leave_max = settings.get("leave_after_max_hours", 6)
    return MSG_HUMANTIC_PANEL.format(
        status=status,
        interval=str(interval).replace(".", "/"),
        leave_min=str(leave_min).replace(".", "/"),
        leave_max=str(leave_max).replace(".", "/"),
    )


async def humantic_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show humantic settings and inline keyboard (entry: button مدیریت رفتار انسانی)."""
    if not await ensure_admin(update, context):
        return
    settings = await db.get_humantic_settings()
    text = _format_panel(settings)
    await update.message.reply_text(
        text,
        reply_markup=humantic_manage_inline(settings),
    )


async def humantic_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline callbacks: hum_on, hum_off, hum_int_*, hum_leave_*."""
    if not await ensure_admin(update, context):
        return
    q = update.callback_query
    await q.answer()
    if not q.data or not q.data.startswith("hum_"):
        return

    data = q.data
    settings = await db.get_humantic_settings()

    if data == "hum_on":
        await db.update_humantic_settings(enabled=True)
        await q.edit_message_text(
            MSG_HUMANTIC_ON + "\n\n" + _format_panel(await db.get_humantic_settings()),
            reply_markup=humantic_manage_inline(await db.get_humantic_settings()),
        )
    elif data == "hum_off":
        await db.update_humantic_settings(enabled=False)
        await q.edit_message_text(
            MSG_HUMANTIC_OFF + "\n\n" + _format_panel(await db.get_humantic_settings()),
            reply_markup=humantic_manage_inline(await db.get_humantic_settings()),
        )
    elif data == "hum_int_1":
        await db.update_humantic_settings(run_interval_hours=1.0)
        settings = await db.get_humantic_settings()
        await q.edit_message_text(
            MSG_HUMANTIC_INTERVAL.format(interval="۱") + "\n\n" + _format_panel(settings),
            reply_markup=humantic_manage_inline(settings),
        )
    elif data == "hum_int_5":
        await db.update_humantic_settings(run_interval_hours=5.0)
        settings = await db.get_humantic_settings()
        await q.edit_message_text(
            MSG_HUMANTIC_INTERVAL.format(interval="۵") + "\n\n" + _format_panel(settings),
            reply_markup=humantic_manage_inline(settings),
        )
    elif data == "hum_int_6":
        await db.update_humantic_settings(run_interval_hours=6.0)
        settings = await db.get_humantic_settings()
        await q.edit_message_text(
            MSG_HUMANTIC_INTERVAL.format(interval="۶") + "\n\n" + _format_panel(settings),
            reply_markup=humantic_manage_inline(settings),
        )
    elif data == "hum_leave_1_3":
        await db.update_humantic_settings(leave_after_min_hours=1.0, leave_after_max_hours=3.0)
        settings = await db.get_humantic_settings()
        await q.edit_message_text(
            MSG_HUMANTIC_LEAVE.format(min_h="۱", max_h="۳") + "\n\n" + _format_panel(settings),
            reply_markup=humantic_manage_inline(settings),
        )
    elif data == "hum_leave_2_6":
        await db.update_humantic_settings(leave_after_min_hours=2.0, leave_after_max_hours=6.0)
        settings = await db.get_humantic_settings()
        await q.edit_message_text(
            MSG_HUMANTIC_LEAVE.format(min_h="۲", max_h="۶") + "\n\n" + _format_panel(settings),
            reply_markup=humantic_manage_inline(settings),
        )
    else:
        await q.edit_message_text(
            _format_panel(settings),
            reply_markup=humantic_manage_inline(settings),
        )
