# it's file for running the humantic actions
# it's automatically run in main.py
# it's run every random minutes between 10 and 30 minutes
import random
import time
from telethon import TelegramClient

from channels import get_channels_list
from chats import get_chats_list
from pv import get_pv_list


def joing_channels():
    channels_list = get_channels_list()
    for channel in channels_list:
        client.join_channel(channel["link"])
        time.sleep(random.randint(10, 30))

def joing_chats():
    chats_list = get_chats_list()
    for chat in chats_list:
        client.join_chat(chat["link"])
        time.sleep(random.randint(10, 30))

def joing_pv():
    pv_list = get_pv_list()
    for p in pv_list:
        client.join_channel(p["link"])