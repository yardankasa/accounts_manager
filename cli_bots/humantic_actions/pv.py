# Here for functions that are Very Carefully Joined to Humantic Actions for Joining
# Into PV  Randomly Selected by the Range 
import json
from core.config import SESSION_DIR
from telethon import TelegramClient

with open("data/links_pool/pv.json", "r") as f:
    pv = json.load(f)["pv"]

def get_pv_list(with_name: bool = False):
    pv_list = []
    for p in pv:
        if with_name:
            pv_list.append({"name": p["name"], "link": p["link"], "id": p["id"]})
        else:
            pv_list.append({"link": p["link"], "id": p["id"]})
    return pv_list


