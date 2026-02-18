# Here for functions that are Very Carefully Joined to Humantic Actions for Joining
# Into Channels  Randomly Selected by the Range 
import json
from core.config import SESSION_DIR
from telethon import TelegramClient

with open("data/links_pool/channels.json", "r") as f:
    channels = json.load(f)["channels"]

def get_channels_list(with_name: bool = False):
    channels_list = []
    for channel in channels:
        if with_name:
            channels_list.append({"name": channel["name"], "link": channel["link"], "id": channel["id"]})
        else:
            channels_list.append({"link": channel["link"], "id": channel["id"]})
    return channels_list
