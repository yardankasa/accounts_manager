"""
Humantic actions v1: simulate a normal user to reduce ban risk.
- Join channels and chats from data/links_pool at random, with calm delays.
- Send one PM to each PV link.
- Runs per account, one account after another, reading accounts from DB (main node).
"""

from .runner import run_all_accounts, run_humantic_for_client, main_sync

__all__ = ["run_all_accounts", "run_humantic_for_client", "main_sync"]
