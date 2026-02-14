"""Persian reply keyboards (normal buttons, no glass)."""
from telegram import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton

# Main admin panel
def main_admin_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("ورود به اکانت")],
            [KeyboardButton("مدیریت نودها")],
            [KeyboardButton("لیست اکانت‌ها")],
            [KeyboardButton("بازگشت / انصراف")],
        ],
        resize_keyboard=True,
    )


def back_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("بازگشت / انصراف")]],
        resize_keyboard=True,
    )


def cancel_keyboard():
    return ReplyKeyboardRemove()


# Node selection: inline with remaining logins (e.g. "نود اصلی ۲/۳")
def node_choice_inline(nodes_with_remaining: list[tuple[int, str, int]]):
    """nodes_with_remaining: list of (node_id, node_name, remaining_today)."""
    buttons = []
    for node_id, name, rem in nodes_with_remaining:
        label = f"{name} ({rem}/۳)"
        buttons.append([InlineKeyboardButton(label, callback_data=f"node_{node_id}")])
    return InlineKeyboardMarkup(buttons) if buttons else None


# Account list: inline delete per account
def account_list_inline(accounts: list[dict]):
    """accounts: list of {id, phone, node_name}."""
    buttons = []
    for a in accounts:
        label = f"{a.get('phone', '')} – {a.get('node_name', '')}"
        buttons.append([InlineKeyboardButton(f"حذف {a.get('phone', '')}", callback_data=f"delacc_{a['id']}")])
    return InlineKeyboardMarkup(buttons) if buttons else None


# Node list for management: inline
def node_manage_inline(nodes: list[dict]):
    """nodes: list of node dicts with id, name."""
    buttons = []
    for n in nodes:
        name = n.get("name", f"نود {n['id']}")
        buttons.append([InlineKeyboardButton(name, callback_data=f"nodemgr_{n['id']}")])
    buttons.append([InlineKeyboardButton("افزودن نود جدید", callback_data="nodemgr_add")])
    return InlineKeyboardMarkup(buttons) if buttons else None


def node_delete_confirm_inline(node_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("بله، حذف کن", callback_data=f"nodedel_yes_{node_id}")],
        [InlineKeyboardButton("خیر، انصراف", callback_data="nodedel_no")],
    ])
