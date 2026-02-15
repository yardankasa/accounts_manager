#!/usr/bin/env python3
"""
Send messages to a bot from account session. Runs on remote node.
Reads API_ID, API_HASH, SESSION_PATH, BOT_USERNAME, MSG1, MSG2 from env.
Outputs: OK or ERROR <message>
"""
import os
import sys


def main() -> None:
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    session_path = os.getenv("SESSION_PATH")
    bot_username = os.getenv("BOT_USERNAME", "").lstrip("@")
    msg1 = os.getenv("MSG1", "/start")
    msg2 = os.getenv("MSG2")
    if not all([api_id, api_hash, session_path, bot_username]):
        print("ERROR Missing env: API_ID, API_HASH, SESSION_PATH, BOT_USERNAME", flush=True)
        sys.exit(1)
    try:
        api_id = int(api_id)
    except ValueError:
        print("ERROR API_ID must be integer", flush=True)
        sys.exit(1)

    from telethon.sync import TelegramClient

    try:
        with TelegramClient(session_path, api_id, api_hash) as client:
            if not client.is_user_authorized():
                print("ERROR Session not authorized", flush=True)
                sys.exit(1)
            bot = client.get_entity(bot_username)
            client.send_message(bot, msg1)
            if msg2:
                client.send_message(bot, msg2)
            print("OK", flush=True)
    except Exception as e:
        print(f"ERROR {str(e)[:150]}", flush=True)
        sys.exit(1)
