"""Tasks runner config: links file, log path and calm delays."""
from pathlib import Path

from core.config import DATA_DIR, LOGS_DIR

# JSON with task bots: {"bot_links": [{ "name": "...", "link": "https://t.me/SomeBot", "id": -100 }, ...]}
TASKS_LINKS_FILE: Path = DATA_DIR / "links_pool" / "tasks_links.json"

# Dedicated tasks log file (per-account messages will include session name).
TASKS_LOG_FILE: Path = LOGS_DIR / "tasks.log"

# How many recent messages to scan after /stars
MESSAGES_LIMIT = 15

# Delays (seconds) — kept calm to avoid flood
DELAY_AFTER_STARS_MIN = 2
DELAY_AFTER_STARS_MAX = 5
DELAY_BEFORE_CONFIRM_MIN = 2
DELAY_BEFORE_CONFIRM_MAX = 4

# Confirm attempts per task message
MAX_CONFIRM_ATTEMPTS = 2

