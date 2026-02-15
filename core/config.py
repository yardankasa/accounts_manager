"""Load .env from application root and expose config."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Application root: directory containing core/, main.py, .env (parent of core/)
# All dirs (data, logs) are under this root.
_APP_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_APP_ROOT / ".env", verbose=True)

def get_env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()

def get_int(key: str, default: int = 0) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default

# Bot
BOT_TOKEN = get_env("BOT_TOKEN")
# Optional proxy (e.g. socks5://127.0.0.1:10808). Leave empty for no proxy.
# If set, this is used for the bot; env vars HTTP_PROXY/HTTPS_PROXY are ignored for the bot.
PROXY_URL = get_env("PROXY_URL")
API_ID = get_int("API_ID")
API_HASH = get_env("API_HASH")
ADMIN_IDS_STR = get_env("ADMIN_IDS")  # comma-separated for bootstrap
# Bot username (without @) - accounts send /im_alive_ to this bot. Example: StarsRM_bot
BOT_USERNAME = get_env("BOT_USERNAME")
# MySQL
MYSQL_HOST = get_env("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = get_int("MYSQL_PORT", 3306)
MYSQL_USER = get_env("MYSQL_USER", "rezabots")
MYSQL_PASSWORD = get_env("MYSQL_PASSWORD")
MYSQL_DATABASE = get_env("MYSQL_DATABASE", "rezabots")

# Paths (all under application root)
DATA_DIR = _APP_ROOT / "data"
SESSION_DIR = DATA_DIR / "session"
LOGS_DIR = _APP_ROOT / "logs"
