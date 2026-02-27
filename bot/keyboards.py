"""Persian reply keyboards with emojis. One-tap back to menu."""
from telegram import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton

# Use when editing a message that had inline keyboard: pass this to clear buttons.
inline_keyboard_clear = InlineKeyboardMarkup([])

# Single label for "back to main menu" – easy to tap, same everywhere
BACK_TO_MENU = "🏠 بازگشت به منو"
# Login button text – use same string for handler matching
LOGIN_BUTTON = "Account Loginer"

# Humantic actions admin button
HUMANTIC_BUTTON = "مدیریت رفتار انسانی"

def main_admin_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(LOGIN_BUTTON)],
            [KeyboardButton("🖥 مدیریت نودها")],
            [KeyboardButton("📋 لیست اکانت‌ها")],
            [KeyboardButton(HUMANTIC_BUTTON)],
            [KeyboardButton(BACK_TO_MENU)],
        ],
        resize_keyboard=True,
    )


def back_keyboard():
    """During login/flow: one button to go back to main menu."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BACK_TO_MENU)]],
        resize_keyboard=True,
    )


def cancel_keyboard():
    return ReplyKeyboardRemove()


# Node selection: inline with remaining logins (rem in Persian digits)
def node_choice_inline(nodes_with_remaining: list[tuple[int, str, int]]):
    from .messages import fa_num
    buttons = []
    for node_id, name, rem in nodes_with_remaining:
        label = f"🖥 {name} ({fa_num(rem)}/۳)"
        buttons.append([InlineKeyboardButton(label, callback_data=f"node_{node_id}")])
    return InlineKeyboardMarkup(buttons) if buttons else None


def account_list_inline(accounts: list[dict]):
    buttons = []
    for a in accounts:
        phone = a.get("phone", "")
        row = [
            InlineKeyboardButton("📊 وضعیت", callback_data=f"statusacc_{a['id']}"),
            InlineKeyboardButton(f"🗑 حذف {phone}", callback_data=f"delacc_{a['id']}"),
        ]
        buttons.append(row)
    return InlineKeyboardMarkup(buttons) if buttons else None


def account_delete_confirm_inline(account_id: int):
    """Confirmation: Yes / No."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ بله، حذف کن", callback_data=f"delacc_confirm_{account_id}")],
        [InlineKeyboardButton("❌ خیر، انصراف", callback_data="delacc_cancel")],
    ])


def node_manage_inline(nodes: list[dict]):
    """Legacy stub (multi-node mode removed). Not used in single-server mode."""
    return InlineKeyboardMarkup([])


def node_delete_confirm_inline(node_id: int):
    """Legacy stub; node deletion is no longer supported."""
    return InlineKeyboardMarkup([])


def node_delete_final_inline(node_id: int):
    """Legacy stub; node deletion is no longer supported."""
    return InlineKeyboardMarkup([])


def node_main_no_delete_inline():
    """Legacy stub; only main node exists in single-server mode."""
    return InlineKeyboardMarkup([])


# --- Humantic actions (مدیریت رفتار انسانی) ---
# Sections with fewer buttons per row for clarity

# Interval: (min_h, max_h, suffix, label)
HUMANTIC_INTERVAL_PRESETS = [
    (4, 6, "4_6", "۴–۶ س"),
    (8, 12, "8_12", "۸–۱۲ س"),
    (24, 30, "24_30", "۱ روز"),
]
# Account deep sleep (days): (min_days, max_days, suffix, label)
HUMANTIC_SLEEP_ACC_PRESETS = [
    (1, 2, "1_2", "۱–۲ روز"),
    (2, 3, "2_3", "۲–۳ روز"),
    (3, 5, "3_5", "۳–۵ روز"),
    (5, 7, "5_7", "۵–۷ روز"),
    (7, 10, "7_10", "۷–۱۰ روز"),
]
# System deep sleep (hours): (min_hours, max_hours, suffix, label)
HUMANTIC_SLEEP_SYS_PRESETS = [
    (0.5, 1.0, "0_5_1", "۰.۵–۱ س"),
    (1.0, 1.5, "1_1_5", "۱–۱.۵ س"),
    (1.5, 2.0, "1_5_2", "۱.۵–۲ س"),
    (2.0, 3.0, "2_3", "۲–۳ س"),
]

def humantic_manage_inline(settings: dict):
    """Sectioned keyboard: 1–2 buttons per row for easier reading."""
    enabled = settings.get("enabled", False)
    min_h = float(settings.get("run_interval_min_hours") or 4)
    max_h = float(settings.get("run_interval_max_hours") or 6)
    acc_sleep_min = float(settings.get("account_sleep_min_days") or settings.get("account_sleep_days") or 3)
    acc_sleep_max = float(settings.get("account_sleep_max_days") or settings.get("account_sleep_days") or 5)
    sys_sleep_min = float(settings.get("system_sleep_min_hours") or settings.get("system_sleep_hours") or 0.5)
    sys_sleep_max = float(settings.get("system_sleep_max_hours") or settings.get("system_sleep_hours") or 2.0)
    leave_enabled = bool(settings.get("leave_enabled", True))
    acc_sleep_enabled = bool(settings.get("account_sleep_enabled", True))
    sys_sleep_enabled = bool(settings.get("system_sleep_enabled", True))
    # Section 1: وضعیت
    row_status = [
        InlineKeyboardButton("✅ روشن" + ("" if not enabled else " ✓"), callback_data="hum_on"),
        InlineKeyboardButton("❌ خاموش" + ("" if enabled else " ✓"), callback_data="hum_off"),
    ]
    # Section 2: فاصله اجرا — 2 then 1 per row
    row_int1 = []
    for lo, hi, suffix, label in HUMANTIC_INTERVAL_PRESETS[:2]:
        is_cur = abs((min_h - lo) + (max_h - hi)) < 0.1
        row_int1.append(InlineKeyboardButton(label + (" ✓" if is_cur else ""), callback_data=f"hum_int_{suffix}"))
    row_int2 = []
    for lo, hi, suffix, label in HUMANTIC_INTERVAL_PRESETS[2:]:
        is_cur = abs((min_h - lo) + (max_h - hi)) < 0.1
        row_int2.append(InlineKeyboardButton(label + (" ✓" if is_cur else ""), callback_data=f"hum_int_{suffix}"))
    # Section 3: ترک (leave channels/chats after X hours) — toggle + presets
    row_leave_toggle = [
        InlineKeyboardButton("ترک روشن" + (" ✓" if leave_enabled else ""), callback_data="hum_leave_on"),
        InlineKeyboardButton("ترک خاموش" + ("" if leave_enabled else " ✓"), callback_data="hum_leave_off"),
    ]
    leave_min = float(settings.get("leave_after_min_hours") or 2)
    leave_max = float(settings.get("leave_after_max_hours") or 6)
    row_leave = [
        InlineKeyboardButton("۱–۳ س" + (" ✓" if leave_min == 1 and leave_max == 3 else ""), callback_data="hum_leave_1_3"),
        InlineKeyboardButton("۲–۶ س" + (" ✓" if leave_min == 2 and leave_max == 6 else ""), callback_data="hum_leave_2_6"),
        InlineKeyboardButton("۲۵–۳۰ س" + (" ✓" if leave_min == 25 and leave_max == 30 else ""), callback_data="hum_leave_25_30"),
    ]
    # Section 4: خواب اکانت — toggle + 2 then 3 per row
    row_acc_toggle = [
        InlineKeyboardButton("خواب اکانت روشن" + (" ✓" if acc_sleep_enabled else ""), callback_data="hum_sleep_acc_on"),
        InlineKeyboardButton("خواب اکانت خاموش" + ("" if acc_sleep_enabled else " ✓"), callback_data="hum_sleep_acc_off"),
    ]
    row_acc1 = []
    for min_d, max_d, suffix, label in HUMANTIC_SLEEP_ACC_PRESETS[:2]:
        is_cur = abs(acc_sleep_min - min_d) < 0.1 and abs(acc_sleep_max - max_d) < 0.1
        row_acc1.append(InlineKeyboardButton(label + (" ✓" if is_cur else ""), callback_data=f"hum_sleep_acc_{suffix}"))
    row_acc2 = []
    for min_d, max_d, suffix, label in HUMANTIC_SLEEP_ACC_PRESETS[2:]:
        is_cur = abs(acc_sleep_min - min_d) < 0.1 and abs(acc_sleep_max - max_d) < 0.1
        row_acc2.append(InlineKeyboardButton(label + (" ✓" if is_cur else ""), callback_data=f"hum_sleep_acc_{suffix}"))
    # Section 5: خواب سیستم (ساعتی) — toggle + 2 per row
    row_sys_toggle = [
        InlineKeyboardButton("خواب سیستم روشن" + (" ✓" if sys_sleep_enabled else ""), callback_data="hum_sleep_sys_on"),
        InlineKeyboardButton("خواب سیستم خاموش" + ("" if sys_sleep_enabled else " ✓"), callback_data="hum_sleep_sys_off"),
    ]
    row_sys1 = []
    for min_h, max_h, suffix, label in HUMANTIC_SLEEP_SYS_PRESETS[:2]:
        is_cur = abs(sys_sleep_min - min_h) < 0.1 and abs(sys_sleep_max - max_h) < 0.1
        row_sys1.append(InlineKeyboardButton(label + (" ✓" if is_cur else ""), callback_data=f"hum_sleep_sys_{suffix}"))
    row_sys2 = []
    for min_h, max_h, suffix, label in HUMANTIC_SLEEP_SYS_PRESETS[2:]:
        is_cur = abs(sys_sleep_min - min_h) < 0.1 and abs(sys_sleep_max - max_h) < 0.1
        row_sys2.append(InlineKeyboardButton(label + (" ✓" if is_cur else ""), callback_data=f"hum_sleep_sys_{suffix}"))
    return InlineKeyboardMarkup([
        row_status,
        row_int1,
        row_int2,
        row_leave_toggle,
        row_leave,
        row_acc_toggle,
        row_acc1,
        row_acc2,
        row_sys_toggle,
        row_sys1,
        row_sys2,
    ])
