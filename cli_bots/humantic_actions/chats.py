# Here for functions that are Very Carefully Joined to Humantic Actions for Joining
# Into Chats  Randomly Selected by the Range 
import json
from core.config import SESSION_DIR
from telethon import TelegramClient

with open("data/links_pool/chats.json", "r") as f:
    chats = json.load(f)["chats"]

def get_chats_list(with_name: bool = False):
    chats_list = []
    for chat in chats:
        if with_name:
            chats_list.append({"name": chat["name"], "link": chat["link"], "id": chat["id"]})
        else:
            chats_list.append({"link": chat["link"], "id": chat["id"]})
    return chats_list

