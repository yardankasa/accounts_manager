#!/usr/bin/env python3
"""
Telethon login worker for nodes. Reads API_ID, API_HASH, TELEGRAM_PHONE, SESSION_BASE from env.
Communicates via stdout/stdin:
  stdout: NEED_CODE -> then read one line from stdin (code)
  stdout: NEED_2FA -> then read one line from stdin (password)
  stdout: OK <session_path> on success
  stdout: ERROR <message> on failure
Uses sync Telethon so we can block on stdin.
"""
import os
import sys
from pathlib import Path

def main() -> None:
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    phone = os.getenv("TELEGRAM_PHONE")
    session_base = os.getenv("SESSION_BASE")
    if not all([api_id, api_hash, phone, session_base]):
        print("ERROR Missing env: API_ID, API_HASH, TELEGRAM_PHONE, SESSION_BASE", flush=True)
        sys.exit(1)
    try:
        api_id = int(api_id)
    except ValueError:
        print("ERROR API_ID must be integer", flush=True)
        sys.exit(1)

    from telethon.sync import TelegramClient
    from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError, PasswordHashInvalidError

    base = Path(session_base)
    base.mkdir(parents=True, exist_ok=True)
    session_name = "".join(c for c in phone if c.isdigit()) or "session"
    session_path = str(base / session_name)

    with TelegramClient(session_path, api_id, api_hash) as client:
        try:
            if not client.is_user_authorized():
                client.send_code_request(phone)
                print("NEED_CODE", flush=True)
                code = sys.stdin.readline()
                if not code:
                    print("ERROR No code received", flush=True)
                    sys.exit(1)
                code = code.strip()
                try:
                    client.sign_in(phone, code)
                except SessionPasswordNeededError:
                    print("NEED_2FA", flush=True)
                    pwd = sys.stdin.readline()
                    if not pwd:
                        print("ERROR No password received", flush=True)
                        sys.exit(1)
                    try:
                        client.sign_in(password=pwd.strip())
                    except PasswordHashInvalidError:
                        print("ERROR Invalid 2FA password", flush=True)
                        sys.exit(1)
                except (PhoneCodeInvalidError, PhoneCodeExpiredError) as e:
                    print(f"ERROR {e}", flush=True)
                    sys.exit(1)
            print(f"OK {session_path}", flush=True)
        except Exception as e:
            print(f"ERROR {e}", flush=True)
            sys.exit(1)


if __name__ == "__main__":
    main()
