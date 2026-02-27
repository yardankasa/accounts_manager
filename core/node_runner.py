"""Node runner for main (local) node.

در نسخه فعلی معماری چندنودی و SSH حذف شده و فقط «نود اصلی» که روی همین
سرور است استفاده می‌شود. این ماژول فقط عملیات روی همان نود اصلی را
انجام می‌دهد و برای نودهای دیگر صرفاً پیام خطا برمی‌گرداند تا به‌صورت
ایمن مشخص شود که دیگر پشتیبانی نمی‌شوند.
"""

import logging
from pathlib import Path
from typing import Awaitable, Callable

from . import db

logger = logging.getLogger(__name__)


async def check_node_connection(node: dict) -> tuple[bool, str]:
    """Check readiness of main node; remote nodes are no longer supported."""
    logger.info("[NODE_RUNNER] check_node_connection(node_id=%s, is_main=%s)", node.get("id"), node.get("is_main"))
    if node.get("is_main"):
        from .config import SESSION_DIR

        try:
            SESSION_DIR.mkdir(parents=True, exist_ok=True)
            return True, "نود اصلی (همین سرور) آماده است."
        except Exception:
            logger.exception("Main node session dir check failed")
            return False, "خطا در ایجاد پوشهٔ نشست روی سرور اصلی."
    # Any non-main node is considered legacy/unsupported
    return False, "این نسخه فقط روی سرور اصلی کار می‌کند؛ نودهای SSH دیگر پشتیبانی نمی‌شوند."


async def run_login_on_node(
    node_id: int,
    phone: str,
    session_base_path: str,
    api_id: int,
    api_hash: str,
    code_callback: Callable[[], Awaitable[str]],
    password_callback: Callable[[], Awaitable[str | None]],
) -> tuple[bool, str, str | None]:
    """Run Telethon login.

    در نسخه فعلی فقط نود اصلی (روی همین سرور) پشتیبانی می‌شود.
    api_id, api_hash: اعتبارهای هر اکانت (از کاربر، نه از .env).
    code_callback: تابع async که کد را برمی‌گرداند.
    password_callback: تابع async که رمز دو مرحله‌ای (یا None) را برمی‌گرداند.
    خروجی: (موفقیت، پیام فارسی، مسیر سشن یا None).
    """
    logger.info("[NODE_RUNNER] run_login_on_node(node_id=%s, phone=%s)", node_id, phone[:6] if len(phone) >= 6 else "***")
    node = await db.get_node(node_id)
    if not node:
        return False, "نود یافت نشد.", None
    if not node.get("is_main"):
        # Safety path for قدیمی‌ها
        logger.warning("run_login_on_node called for non-main node_id=%s; multi-node is no longer supported.", node_id)
        return False, "این نسخه فقط از نود اصلی روی همین سرور پشتیبانی می‌کند.", None
    # Run locally via core.telethon_login
    from . import telethon_login

    return await telethon_login.run_login_main(
        session_base_path=session_base_path,
        phone=phone,
        api_id=api_id,
        api_hash=api_hash,
        code_callback=code_callback,
        password_callback=password_callback,
    )


async def delete_session_on_node(node: dict, session_path: str) -> None:
    """Delete old session files before re-login (only local main node)."""
    p = Path(session_path)
    if not p.exists():
        return
    for f in p.parent.glob(p.name + "*"):
        try:
            f.unlink()
        except OSError:
            pass


async def send_messages_to_bot_on_node(
    node: dict,
    session_path: str,
    api_id: int,
    api_hash: str,
    bot_username: str,
    messages: list[str],
) -> tuple[bool, str]:
    """Use the account's session to send messages to a bot (main node only)."""
    if not messages:
        return False, "No messages"
    if not node.get("is_main"):
        logger.warning("send_messages_to_bot_on_node called for non-main node; multi-node is disabled.")
        return False, "فقط نود اصلی (همین سرور) برای ارسال پیام پشتیبانی می‌شود."
    from . import session_status

    return await session_status.send_messages_to_bot(
        session_path, api_id, api_hash, bot_username, messages
    )


async def check_session_on_node(
    node: dict,
    session_path: str,
    api_id: int,
    api_hash: str,
) -> tuple[bool, str]:
    """Check if session is active (main node only)."""
    if not node.get("is_main"):
        logger.warning("check_session_on_node called for non-main node; multi-node is disabled.")
        return False, "این نسخه فقط وضعیت سشن روی نود اصلی را بررسی می‌کند."
    from . import session_status

    ok, err = await session_status.check_session_status(session_path, api_id, api_hash)
    return ok, err or ""
