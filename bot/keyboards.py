"""Persian reply keyboards with emojis. One-tap back to menu."""
from telegram import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton

# Use when editing a message that had inline keyboard: pass this to clear buttons.
inline_keyboard_clear = InlineKeyboardMarkup([])

# Single label for "back to main menu" – easy to tap, same everywhere
BACK_TO_MENU = "🏠 بازگشت به منو"
# Login button text – use same string for handler matching
LOGIN_BUTTON = "Account Loginer"

def main_admin_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(LOGIN_BUTTON)],
            [KeyboardButton("🖥 مدیریت نودها")],
            [KeyboardButton("📋 لیست اکانت‌ها")],
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
        label = f"{a.get('phone', '')} – {a.get('node_name', '')}"
        buttons.append([InlineKeyboardButton(f"🗑 حذف {a.get('phone', '')}", callback_data=f"delacc_{a['id']}")])
    return InlineKeyboardMarkup(buttons) if buttons else None


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
    return InlineKeyboardMarkup(buttons) if buttons else None


def node_delete_confirm_inline(node_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ بله، حذف کن", callback_data=f"nodedel_yes_{node_id}")],
        [InlineKeyboardButton("❌ خیر، انصراف", callback_data="nodedel_no")],
    ])


def node_main_no_delete_inline():
    """Only 'back' button when viewing main node (not deletable)."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ بازگشت به لیست", callback_data="nodedel_no")],
    ])
