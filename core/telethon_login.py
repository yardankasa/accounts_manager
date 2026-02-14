"""Run Telethon login on main server (same process)."""
import logging
from pathlib import Path
from typing import Awaitable, Callable

from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    PasswordHashInvalidError,
    PhoneNumberInvalidError,
)

logger = logging.getLogger(__name__)


async def run_login_main(
    session_base_path: str,
    phone: str,
    api_id: int,
    api_hash: str,
    code_callback: Callable[[], Awaitable[str]],
    password_callback: Callable[[], Awaitable[str | None]],
) -> tuple[bool, str, str | None]:
    """
    Run Telethon login locally. api_id/api_hash are per-account (from user).
    Returns (success, message_persian, session_path).
    """
    base = Path(session_base_path)
    base.mkdir(parents=True, exist_ok=True)
    session_name = "".join(c for c in phone if c.isdigit()) or "session"
    session_path = str(base / session_name)
    client = TelegramClient(session_path, api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            try:
                await client.send_code_request(phone)
            except PhoneNumberInvalidError:
                return False, "شماره تلفن معتبر نیست. با کد کشور و بدون فاصله وارد کنید (مثال: 254796276463 یا +254796276463).", None
            code = await code_callback()
            try:
                await client.sign_in(phone, code)
            except SessionPasswordNeededError:
                pwd = await password_callback()
                if not pwd:
                    return False, "رمز دو مرحله‌ای لازم است.", None
                try:
                    await client.sign_in(password=pwd.strip())
                except PasswordHashInvalidError:
                    return False, "رمز دو مرحله‌ای اشتباه است.", None
            except (PhoneCodeInvalidError, PhoneCodeExpiredError) as e:
                logger.warning("Telethon sign_in code error: %s", e)
                return False, "کد اشتباه یا منقضی است. لطفاً کد صحیح را وارد کنید.", None
        me = await client.get_me()
        logger.info("Logged in as %s on main", me.phone)
        return True, "ورود با موفقیت انجام شد.", session_path
    except Exception as e:
        logger.exception("Telethon login failed: %s", e)
        return False, "خطا در ورود: " + str(e)[:150], None
    finally:
        await client.disconnect()
