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
    MSG_HUMANTIC_LEAVE_ON,
    MSG_HUMANTIC_LEAVE_OFF,
    MSG_HUMANTIC_SLEEP_ACC_ON,
    MSG_HUMANTIC_SLEEP_ACC_OFF,
    MSG_HUMANTIC_SLEEP_SYS_ON,
    MSG_HUMANTIC_SLEEP_SYS_OFF,
)

logger = logging.getLogger(__name__)


def _format_panel(settings: dict) -> str:
    actions_status = "روشن ✅" if settings.get("actions_enabled", True) else "خاموش ❌"
    min_h = settings.get("run_interval_min_hours") or settings.get("run_interval_hours") or 4
    max_h = settings.get("run_interval_max_hours") or settings.get("run_interval_hours") or 6
    interval = f"{min_h:.0f}–{max_h:.0f} ساعت"
    leave_min = settings.get("leave_after_min_hours", 2)
    leave_max = settings.get("leave_after_max_hours", 6)
    acc_sleep_min = settings.get("account_sleep_min_days") or settings.get("account_sleep_days") or 3
    acc_sleep_max = settings.get("account_sleep_max_days") or settings.get("account_sleep_days") or 5
    sys_sleep_min = settings.get("system_sleep_min_hours") or settings.get("system_sleep_hours") or 0.5
    sys_sleep_max = settings.get("system_sleep_max_hours") or settings.get("system_sleep_hours") or 2.0
    leave_status = "فعال ✅" if settings.get("leave_enabled", True) else "غیرفعال ❌"
    acc_sleep_status = "فعال ✅" if settings.get("account_sleep_enabled", True) else "غیرفعال ❌"
    sys_sleep_status = "فعال ✅" if settings.get("system_sleep_enabled", True) else "غیرفعال ❌"
    return MSG_HUMANTIC_PANEL.format(
        actions_status=actions_status,
        interval=interval,
        leave_min=str(leave_min).replace(".", "/"),
        leave_max=str(leave_max).replace(".", "/"),
        leave_status=leave_status,
        acc_sleep_status=acc_sleep_status,
        sys_sleep_status=sys_sleep_status,
        account_sleep_days=f"{acc_sleep_min:.0f}–{acc_sleep_max:.0f}",
        system_sleep_hours=f"{sys_sleep_min:.1f}–{sys_sleep_max:.1f}".replace(".", "/"),
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
    """Handle inline callbacks: hum_on/off, hum_int_*, hum_leave_*, hum_sleep_* and toggles."""
    if not await ensure_admin(update, context):
        return
    q = update.callback_query
    await q.answer()
    if not q.data or not q.data.startswith("hum_"):
        return

    data = q.data
    settings = await db.get_humantic_settings()

    if data == "hum_on":
        await db.update_humantic_settings(actions_enabled=True)
        await q.edit_message_text(
            MSG_HUMANTIC_ON + "\n\n" + _format_panel(await db.get_humantic_settings()),
            reply_markup=humantic_manage_inline(await db.get_humantic_settings()),
        )
    elif data == "hum_off":
        await db.update_humantic_settings(actions_enabled=False)
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
    elif data == "hum_leave_25_30":
        await db.update_humantic_settings(leave_after_min_hours=25.0, leave_after_max_hours=30.0)
        settings = await db.get_humantic_settings()
        await q.edit_message_text(
            MSG_HUMANTIC_LEAVE.format(min_h="۲۵", max_h="۳۰") + "\n\n" + _format_panel(settings),
            reply_markup=humantic_manage_inline(settings),
        )
    elif data.startswith("hum_sleep_acc_"):
        from bot.keyboards import HUMANTIC_SLEEP_ACC_PRESETS
        suffix = data.replace("hum_sleep_acc_", "")
        for min_days, max_days, s, label in HUMANTIC_SLEEP_ACC_PRESETS:
            if s == suffix:
                await db.update_humantic_settings(
                    account_sleep_min_days=min_days,
                    account_sleep_max_days=max_days,
                    account_sleep_days=(min_days + max_days) / 2,  # Keep for backward compatibility
                )
                settings = await db.get_humantic_settings()
                await q.edit_message_text(
                    MSG_HUMANTIC_SLEEP_ACC.format(days=label) + "\n\n" + _format_panel(settings),
                    reply_markup=humantic_manage_inline(settings),
                )
                break
    elif data.startswith("hum_sleep_sys_"):
        from bot.keyboards import HUMANTIC_SLEEP_SYS_PRESETS
        suffix = data.replace("hum_sleep_sys_", "")
        for min_hours, max_hours, s, label in HUMANTIC_SLEEP_SYS_PRESETS:
            if s == suffix:
                await db.update_humantic_settings(
                    system_sleep_min_hours=min_hours,
                    system_sleep_max_hours=max_hours,
                    system_sleep_hours=(min_hours + max_hours) / 2,  # Keep for backward compatibility
                )
                settings = await db.get_humantic_settings()
                await q.edit_message_text(
                    MSG_HUMANTIC_SLEEP_SYS.format(hours=label) + "\n\n" + _format_panel(settings),
                    reply_markup=humantic_manage_inline(settings),
                )
                break
    elif data == "hum_leave_on":
        await db.update_humantic_settings(leave_enabled=True)
        settings = await db.get_humantic_settings()
        await q.edit_message_text(
            MSG_HUMANTIC_LEAVE_ON + "\n\n" + _format_panel(settings),
            reply_markup=humantic_manage_inline(settings),
        )
    elif data == "hum_leave_off":
        await db.update_humantic_settings(leave_enabled=False)
        settings = await db.get_humantic_settings()
        await q.edit_message_text(
            MSG_HUMANTIC_LEAVE_OFF + "\n\n" + _format_panel(settings),
            reply_markup=humantic_manage_inline(settings),
        )
    elif data == "hum_sleep_acc_on":
        await db.update_humantic_settings(account_sleep_enabled=True)
        settings = await db.get_humantic_settings()
        await q.edit_message_text(
            MSG_HUMANTIC_SLEEP_ACC_ON + "\n\n" + _format_panel(settings),
            reply_markup=humantic_manage_inline(settings),
        )
    elif data == "hum_sleep_acc_off":
        await db.update_humantic_settings(account_sleep_enabled=False)
        settings = await db.get_humantic_settings()
        await q.edit_message_text(
            MSG_HUMANTIC_SLEEP_ACC_OFF + "\n\n" + _format_panel(settings),
            reply_markup=humantic_manage_inline(settings),
        )
    elif data == "hum_sleep_sys_on":
        await db.update_humantic_settings(system_sleep_enabled=True)
        settings = await db.get_humantic_settings()
        await q.edit_message_text(
            MSG_HUMANTIC_SLEEP_SYS_ON + "\n\n" + _format_panel(settings),
            reply_markup=humantic_manage_inline(settings),
        )
    elif data == "hum_sleep_sys_off":
        await db.update_humantic_settings(system_sleep_enabled=False)
        settings = await db.get_humantic_settings()
        await q.edit_message_text(
            MSG_HUMANTIC_SLEEP_SYS_OFF + "\n\n" + _format_panel(settings),
            reply_markup=humantic_manage_inline(settings),
        )
    else:
        await q.edit_message_text(
            _format_panel(settings),
            reply_markup=humantic_manage_inline(settings),
        )
