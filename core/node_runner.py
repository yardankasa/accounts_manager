"""SSH to nodes and run login script; bridge stdin/stdout with bot."""
import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Awaitable, Callable

import asyncssh

from . import db
from .config import _APP_ROOT

logger = logging.getLogger(__name__)

# Login worker script path (on main server; we'll copy or reference it for nodes)
LOGIN_WORKER_NAME = "login_worker.py"
# When running on node, we assume the script is at same relative path or installed
LOGIN_WORKER_REMOTE_PATH = "rezabots_login_worker.py"  # deploy this to node; or run via python -c "..." / ssh with script stdin


async def check_node_connection(node: dict) -> tuple[bool, str]:
    """Returns (success, message_in_persian)."""
    logger.info("[NODE_RUNNER] check_node_connection(node_id=%s, is_main=%s)", node.get("id"), node.get("is_main"))
    if node.get("is_main"):
        # Main node: check local session dir
        from .config import SESSION_DIR
        try:
            SESSION_DIR.mkdir(parents=True, exist_ok=True)
            return True, "نود اصلی آماده است."
        except Exception as e:
            logger.exception("Main node session dir check failed")
            return False, "خطا در ایجاد پوشهٔ نشست روی سرور اصلی."
    host = node.get("ssh_host")
    user = node.get("ssh_user")
    port = int(node.get("ssh_port") or 22)
    if not host or not user:
        return False, "نود پیکربندی نشده (میز یا کاربر SSH مشخص نیست)."
    try:
        kwargs = {
            "host": host,
            "port": port,
            "username": user,
        }
        if node.get("ssh_key_path"):
            kwargs["client_keys"] = [node["ssh_key_path"]]
        elif node.get("ssh_password"):
            kwargs["password"] = node["ssh_password"]
        else:
            return False, "برای نود کلید یا رمز SSH تنظیم نشده."
        conn = await asyncio.wait_for(
            asyncssh.connect(**kwargs),
            timeout=15,
        )
        # Quick test: run true
        result = await conn.run("echo OK")
        conn.close()
        if result.exit_status == 0 and "OK" in (result.stdout or ""):
            return True, "اتصال به نود برقرار است."
        return False, "دستور آزمایش روی نود ناموفق بود."
    except asyncio.TimeoutError:
        return False, "اتصال به نود زمان‌گذشت. لطفاً بعداً تلاش کنید."
    except Exception as e:
        logger.exception("Node connection check failed: %s", e)
        return False, "خطا در اتصال به نود: " + str(e)[:100]


async def run_login_on_node(
    node_id: int,
    phone: str,
    session_base_path: str,
    api_id: int,
    api_hash: str,
    code_callback: Callable[[], Awaitable[str]],
    password_callback: Callable[[], Awaitable[str | None]],
) -> tuple[bool, str, str | None]:
    """
    Run Telethon login on remote node. Uses login_worker.py on node.
    api_id, api_hash: per-account credentials (from user, not .env).
    code_callback: async function that returns the code when asked.
    password_callback: async function that returns 2FA password or None.
    Returns (success, message_persian, session_path_on_node or None).
    """
    logger.info("[NODE_RUNNER] run_login_on_node(node_id=%s, phone=%s)", node_id, phone[:6] if len(phone) >= 6 else "***")
    node = await db.get_node(node_id)
    if not node:
        return False, "نود یافت نشد.", None
    if node.get("is_main"):
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
    # Remote: SSH and run worker script
    host = node["ssh_host"]
    user = node["ssh_user"]
    port = int(node.get("ssh_port") or 22)
    kwargs = {"host": host, "port": port, "username": user}
    if node.get("ssh_key_path"):
        kwargs["client_keys"] = [node["ssh_key_path"]]
    elif node.get("ssh_password"):
        kwargs["password"] = node["ssh_password"]
    else:
        return False, "کلید یا رمز SSH برای نود تنظیم نشده.", None

    worker_path = _APP_ROOT / "scripts" / "login_worker.py"
    
    if not worker_path.exists():
        return False, "اسکریپت ورود روی سرور یافت نشد.", None

    script_content = worker_path.read_text()
    remote_script_path = f"/tmp/rezabots_login_worker_{node_id}.py"

    try:
        conn = await asyncio.wait_for(asyncssh.connect(**kwargs), timeout=15)
        try:
            async with conn.start_sftp_client() as sftp:
                with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                    f.write(script_content)
                    local_path = f.name
                try:
                    await sftp.put(local_path, remote_script_path)
                finally:
                    Path(local_path).unlink(missing_ok=True)
            process = await conn.create_process(
                f"python3 -u {remote_script_path}",
                env={"API_ID": str(api_id), "API_HASH": api_hash, "TELEGRAM_PHONE": phone, "SESSION_BASE": session_base_path},
            )
            return await _bridge_process(process, code_callback, password_callback, session_base_path, phone)
        finally:
            conn.close()
    except asyncio.TimeoutError:
        return False, "اتصال به نود زمان‌گذشت.", None
    except Exception as e:
        logger.exception("Run login on node failed: %s", e)
        return False, "خطا در اجرای ورود روی نود: " + str(e)[:80], None


async def _bridge_process(process, code_callback, password_callback, session_base_path: str, phone: str):
    """Read process stdout line by line; when NEED_CODE/NEED_2FA, call callback and write to stdin."""
    session_path = None
    buf = ""
    while True:
        try:
            data = await asyncio.wait_for(process.stdout.read(1024), timeout=60.0)
            if not data:
                break
            buf += data.decode("utf-8", errors="replace")
        except asyncio.TimeoutError:
            # Check if process exited
            if process.exit_status is not None:
                break
            continue
        while "\n" in buf or "OK" in buf or "NEED_CODE" in buf or "NEED_2FA" in buf or "ERROR" in buf:
            line, _, buf = buf.partition("\n")
            line = line.strip()
            if not line:
                continue
            if line == "NEED_CODE":
                code = await code_callback()
                process.stdin.write(code.strip() + "\n")
                await process.stdin.drain()
            elif line == "NEED_2FA":
                pwd = await password_callback()
                if pwd is None:
                    process.stdin.write("\n")
                else:
                    process.stdin.write(pwd.strip() + "\n")
                await process.stdin.drain()
            elif line.startswith("OK "):
                session_path = line[3:].strip()
                break
            elif line.startswith("ERROR "):
                return False, "خطا: " + line[6:].strip()[:200], None
        if session_path is not None:
            break
    # Wait for process to exit
    await asyncio.wait_for(process.wait(), timeout=5)
    if session_path:
        return True, "ورود با موفقیت انجام شد.", session_path
    return False, "ورود تکمیل نشد.", None
