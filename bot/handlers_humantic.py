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
    MSG_HUMANTIC_SLEEP_ACC,
    MSG_HUMANTIC_SLEEP_SYS,
)

logger = logging.getLogger(__name__)


def _format_panel(settings: dict) -> str:
    status = "روشن ✅" if settings.get("enabled") else "خاموش ❌"
    min_h = settings.get("run_interval_min_hours") or settings.get("run_interval_hours") or 4
    max_h = settings.get("run_interval_max_hours") or settings.get("run_interval_hours") or 6
    interval = f"{min_h:.0f}–{max_h:.0f} ساعت"
    leave_min = settings.get("leave_after_min_hours", 2)
    leave_max = settings.get("leave_after_max_hours", 6)
    acc_sleep = settings.get("account_sleep_days", 3)
    sys_sleep_h = settings.get("system_sleep_hours") or 1
    return MSG_HUMANTIC_PANEL.format(
        status=status,
        interval=interval,
        leave_min=str(leave_min).replace(".", "/"),
        leave_max=str(leave_max).replace(".", "/"),
        account_sleep_days=str(acc_sleep).replace(".", "/"),
        system_sleep_hours=str(sys_sleep_h).replace(".", "/"),
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
    elif data == "hum_int_4_6":
        await db.update_humantic_settings(run_interval_min_hours=4.0, run_interval_max_hours=6.0, run_interval_hours=5.0)
        settings = await db.get_humantic_settings()
        await q.edit_message_text(
            MSG_HUMANTIC_INTERVAL.format(interval="۴–۶ ساعت") + "\n\n" + _format_panel(settings),
            reply_markup=humantic_manage_inline(settings),
        )
    elif data == "hum_int_8_12":
        await db.update_humantic_settings(run_interval_min_hours=8.0, run_interval_max_hours=12.0, run_interval_hours=10.0)
        settings = await db.get_humantic_settings()
        await q.edit_message_text(
            MSG_HUMANTIC_INTERVAL.format(interval="۸–۱۲ ساعت") + "\n\n" + _format_panel(settings),
            reply_markup=humantic_manage_inline(settings),
        )
    elif data == "hum_int_24_30":
        await db.update_humantic_settings(run_interval_min_hours=24.0, run_interval_max_hours=30.0, run_interval_hours=24.0)
        settings = await db.get_humantic_settings()
        await q.edit_message_text(
            MSG_HUMANTIC_INTERVAL.format(interval="۱ روز") + "\n\n" + _format_panel(settings),
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
    elif data == "hum_leave_25":
        await db.update_humantic_settings(leave_after_min_hours=25.0, leave_after_max_hours=25.0)
        settings = await db.get_humantic_settings()
        await q.edit_message_text(
            MSG_HUMANTIC_LEAVE.format(min_h="۲۵", max_h="۲۵") + "\n\n" + _format_panel(settings),
            reply_markup=humantic_manage_inline(settings),
        )
    elif data.startswith("hum_sleep_acc_"):
        from bot.keyboards import HUMANTIC_SLEEP_ACC_PRESETS
        suffix = data.replace("hum_sleep_acc_", "")
        for days, s, _ in HUMANTIC_SLEEP_ACC_PRESETS:
            if s == suffix:
                await db.update_humantic_settings(account_sleep_days=days)
                settings = await db.get_humantic_settings()
                label = "۱" if days == 1 else "۲" if days == 2 else "۳" if days == 3 else "۵" if days == 5 else "۷"
                await q.edit_message_text(
                    MSG_HUMANTIC_SLEEP_ACC.format(days=label) + "\n\n" + _format_panel(settings),
                    reply_markup=humantic_manage_inline(settings),
                )
                break
    elif data.startswith("hum_sleep_sys_"):
        from bot.keyboards import HUMANTIC_SLEEP_SYS_PRESETS
        suffix = data.replace("hum_sleep_sys_", "")
        for hours, s, label in HUMANTIC_SLEEP_SYS_PRESETS:
            if s == suffix:
                await db.update_humantic_settings(system_sleep_hours=hours)
                settings = await db.get_humantic_settings()
                await q.edit_message_text(
                    MSG_HUMANTIC_SLEEP_SYS.format(hours=label) + "\n\n" + _format_panel(settings),
                    reply_markup=humantic_manage_inline(settings),
                )
                break
    else:
        await q.edit_message_text(
            _format_panel(settings),
            reply_markup=humantic_manage_inline(settings),
        )
