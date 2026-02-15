#!/usr/bin/env python3
"""
Check session status on remote node. Reads API_ID, API_HASH, SESSION_PATH from env.
Outputs: ACTIVE or INACTIVE <reason>
"""
import os
import sys


def main() -> None:
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    session_path = os.getenv("SESSION_PATH")
    if not all([api_id, api_hash, session_path]):
        print("INACTIVE Missing env: API_ID, API_HASH, SESSION_PATH", flush=True)
        sys.exit(1)
    try:
        api_id = int(api_id)
    except ValueError:
        print("INACTIVE API_ID must be integer", flush=True)
        sys.exit(1)

    from telethon.sync import TelegramClient

    try:
        with TelegramClient(session_path, api_id, api_hash) as client:
            if not client.is_user_authorized():
                print("INACTIVE Session not authorized", flush=True)
                sys.exit(0)
            me = client.get_me()
            if me:
                print("ACTIVE", flush=True)
            else:
                print("INACTIVE Could not get user", flush=True)
    except Exception as e:
        print(f"INACTIVE {str(e)[:150]}", flush=True)
        sys.exit(0)
