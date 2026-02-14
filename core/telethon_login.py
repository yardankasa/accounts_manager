"""Run Telethon login on main server (same process)."""
import asyncio
import logging
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    PasswordHashInvalidError,
)

from .config import API_ID, API_HASH

logger = logging.getLogger(__name__)


async def run_login_main(
    session_base_path: str,
    phone: str,
    code_callback: "async def () -> str",
    password_callback: "async def () -> str | None",
) -> tuple[bool, str, str | None]:
    """
    Run Telethon login locally. Returns (success, message_persian, session_path).
    """
    base = Path(session_base_path)
    base.mkdir(parents=True, exist_ok=True)
    session_name = "".join(c for c in phone if c.isdigit()) or "session"
    session_path = str(base / session_name)
    client = TelegramClient(session_path, API_ID, API_HASH)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.send_code_request(phone)
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
