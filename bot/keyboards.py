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
    buttons = []
    for n in nodes:
        name = n.get("name", f"نود {n['id']}")
        host = n.get("ssh_host")
        ip_label = "سرور اصلی" if n.get("is_main") else (host or "—")
        # Button: name and IP/host (Telegram button text length limit ~64 chars)
        label = f"🖥 {name} │ {ip_label}" if len(ip_label) < 25 else f"🖥 {name}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"nodemgr_{n['id']}")])
    buttons.append([InlineKeyboardButton("➕ افزودن نود جدید", callback_data="nodemgr_add")])
    buttons.append([InlineKeyboardButton("🔍 بررسی سلامت نودها", callback_data="nodemgr_healthcheck")])
    return InlineKeyboardMarkup(buttons) if buttons else None


def node_delete_confirm_inline(node_id: int):
    """First confirmation: Yes / No."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ بله، حذف کن", callback_data=f"nodedel_yes_{node_id}")],
        [InlineKeyboardButton("❌ خیر، انصراف", callback_data="nodedel_no")],
    ])


def node_delete_final_inline(node_id: int):
    """Second confirmation: final Yes / No."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ بله، حذف کنم", callback_data=f"nodedel_final_{node_id}")],
        [InlineKeyboardButton("❌ خیر، انصراف", callback_data="nodedel_no")],
    ])


def node_main_no_delete_inline():
    """Only 'back' button when viewing main node (not deletable)."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ بازگشت به لیست", callback_data="nodedel_no")],
    ])


# --- Humantic actions (مدیریت رفتار انسانی) ---
# Sections with fewer buttons per row for clarity

# Interval: (min_h, max_h, suffix, label)
HUMANTIC_INTERVAL_PRESETS = [
    (4, 6, "4_6", "۴–۶ س"),
    (8, 12, "8_12", "۸–۱۲ س"),
    (24, 30, "24_30", "۱ روز"),
]
# Account deep sleep (days): (days, suffix, label)
HUMANTIC_SLEEP_ACC_PRESETS = [(1, "1", "۱ روز"), (2, "2", "۲ روز"), (3, "3", "۳ روز"), (5, "5", "۵ روز"), (7, "7", "۷ روز")]
# System deep sleep (hours, 0.5–2): (hours, suffix, label)
HUMANTIC_SLEEP_SYS_PRESETS = [(0.5, "0_5", "۰.۵ س"), (1.0, "1", "۱ س"), (1.5, "1_5", "۱.۵ س"), (2.0, "2", "۲ س")]

def humantic_manage_inline(settings: dict):
    """Sectioned keyboard: 1–2 buttons per row for easier reading."""
    enabled = settings.get("enabled", False)
    min_h = float(settings.get("run_interval_min_hours") or 4)
    max_h = float(settings.get("run_interval_max_hours") or 6)
    acc_sleep = float(settings.get("account_sleep_days") or 3)
    sys_sleep = float(settings.get("system_sleep_hours") or 1)
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
    # Section 3: ترک
    row_leave = [
        InlineKeyboardButton("۱–۳ ساعت", callback_data="hum_leave_1_3"),
        InlineKeyboardButton("۲–۶ ساعت", callback_data="hum_leave_2_6"),
    ]
    # Section 4: خواب اکانت — 2 then 3 per row
    row_acc1 = []
    for days, suffix, label in HUMANTIC_SLEEP_ACC_PRESETS[:2]:
        is_cur = abs(acc_sleep - days) < 0.1
        row_acc1.append(InlineKeyboardButton(label + (" ✓" if is_cur else ""), callback_data=f"hum_sleep_acc_{suffix}"))
    row_acc2 = []
    for days, suffix, label in HUMANTIC_SLEEP_ACC_PRESETS[2:]:
        is_cur = abs(acc_sleep - days) < 0.1
        row_acc2.append(InlineKeyboardButton(label + (" ✓" if is_cur else ""), callback_data=f"hum_sleep_acc_{suffix}"))
    # Section 5: خواب سیستم (ساعتی) — 2 per row
    row_sys1 = []
    for hours, suffix, label in HUMANTIC_SLEEP_SYS_PRESETS[:2]:
        is_cur = abs(sys_sleep - hours) < 0.1
        row_sys1.append(InlineKeyboardButton(label + (" ✓" if is_cur else ""), callback_data=f"hum_sleep_sys_{suffix}"))
    row_sys2 = []
    for hours, suffix, label in HUMANTIC_SLEEP_SYS_PRESETS[2:]:
        is_cur = abs(sys_sleep - hours) < 0.1
        row_sys2.append(InlineKeyboardButton(label + (" ✓" if is_cur else ""), callback_data=f"hum_sleep_sys_{suffix}"))
    return InlineKeyboardMarkup([
        row_status,
        row_int1,
        row_int2,
        row_leave,
        row_acc1,
        row_acc2,
        row_sys1,
        row_sys2,
    ])
