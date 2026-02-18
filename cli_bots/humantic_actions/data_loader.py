"""
Load channels, chats, and PV links from data/links_pool JSON files.
Uses paths from config so it works regardless of cwd.
"""
import json
import logging
from pathlib import Path

from .config import LINKS_POOL_DIR

logger = logging.getLogger(__name__)


def _load_json(key: str, filename: str) -> list[dict]:
    path = LINKS_POOL_DIR / filename
    if not path.exists():
        logger.warning("Links file not found: %s", path)
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get(key, [])
        if not isinstance(items, list):
            return []
        return [x for x in items if isinstance(x, dict) and x.get("link")]
    except Exception as e:
        logger.warning("Failed to load %s: %s", path, e)
        return []


def get_channels_list(with_name: bool = False) -> list[dict]:
    items = _load_json("channels", "channels.json")
    out = []
    for ch in items:
        if with_name:
            out.append({"name": ch.get("name", ""), "link": ch["link"], "id": ch.get("id")})
        else:
            out.append({"link": ch["link"], "id": ch.get("id")})
    return out


def get_chats_list(with_name: bool = False) -> list[dict]:
    items = _load_json("chats", "chats.json")
    out = []
    for c in items:
        if with_name:
            out.append({"name": c.get("name", ""), "link": c["link"], "id": c.get("id")})
        else:
            out.append({"link": c["link"], "id": c.get("id")})
    return out


def get_pv_list(with_name: bool = False) -> list[dict]:
    items = _load_json("pv", "pv.json")
    out = []
    for p in items:
        if with_name:
            out.append({"name": p.get("name", ""), "link": p["link"], "id": p.get("id")})
        else:
            out.append({"link": p["link"], "id": p.get("id")})
    return out
