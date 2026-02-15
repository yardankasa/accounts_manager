#!/usr/bin/env python3
"""
Add account (session) as admin in a channel. Runs on remote node.
Reads API_ID, API_HASH, SESSION_PATH, CHANNEL_ID from env.
Outputs: OK or ERROR <message>
"""
import os
import sys


def main() -> None:
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    session_path = os.getenv("SESSION_PATH")
    channel_id = os.getenv("CHANNEL_ID")
    if not all([api_id, api_hash, session_path, channel_id]):
        print("ERROR Missing env: API_ID, API_HASH, SESSION_PATH, CHANNEL_ID", flush=True)
        sys.exit(1)
    try:
        api_id = int(api_id)
        channel_id = int(channel_id)
    except ValueError:
        print("ERROR API_ID and CHANNEL_ID must be integers", flush=True)
        sys.exit(1)

    from telethon.sync import TelegramClient
    from telethon.tl.functions.channels import EditAdminRequest
    from telethon.tl.types import ChatAdminRights

    try:
        with TelegramClient(session_path, api_id, api_hash) as client:
            if not client.is_user_authorized():
                print("ERROR Session not authorized", flush=True)
                sys.exit(1)
            me = client.get_me()
            if not me:
                print("ERROR Could not get user", flush=True)
                sys.exit(1)
            channel = client.get_entity(channel_id)
            rights = ChatAdminRights(
                change_info=True,
                post_messages=True,
                edit_messages=True,
                delete_messages=True,
                ban_users=True,
                invite_users=True,
                pin_messages=True,
                add_admins=True,
                manage_call=True,
            )
            client(EditAdminRequest(channel=channel, user_id=me, admin_rights=rights, rank="Admin"))
            print("OK", flush=True)
    except Exception as e:
        print(f"ERROR {str(e)[:150]}", flush=True)
        sys.exit(1)
