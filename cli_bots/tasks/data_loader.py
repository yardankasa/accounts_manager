"""Load task bots from data/links_pool/tasks_links.json."""
import json
import logging
from pathlib import Path
from typing import Any

from .config import TASKS_LINKS_FILE

logger = logging.getLogger(__name__)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        logger.warning("Tasks links file not found: %s", path)
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load tasks links from %s: %s", path, e)
        return {}


def get_task_bots(with_name: bool = False) -> list[dict[str, Any]]:
    """Return list of task bots from JSON."""
    data = _load_json(TASKS_LINKS_FILE)
    items = data.get("bot_links") or []
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for bot in items:
        if not isinstance(bot, dict):
            continue
        link = bot.get("link")
        if not link:
            continue
        if with_name:
            out.append(
                {
                    "name": bot.get("name") or "",
                    "link": link,
                    "id": bot.get("id"),
                }
            )
        else:
            out.append(
                {
                    "link": link,
                    "id": bot.get("id"),
                }
            )
    return out

