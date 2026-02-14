"""Load .env from project root and expose config."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Project root: parent of src (src/core -> src -> project root)
_SRC = Path(__file__).resolve().parent.parent
_ROOT = _SRC.parent
load_dotenv(_ROOT / ".env")

def get_env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()

def get_int(key: str, default: int = 0) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default

# Bot
BOT_TOKEN = get_env("BOT_TOKEN")
API_ID = get_int("API_ID")
API_HASH = get_env("API_HASH")
ADMIN_IDS_STR = get_env("ADMIN_IDS")  # comma-separated for bootstrap

# MySQL
MYSQL_HOST = get_env("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = get_int("MYSQL_PORT", 3306)
MYSQL_USER = get_env("MYSQL_USER", "rezabots")
MYSQL_PASSWORD = get_env("MYSQL_PASSWORD")
MYSQL_DATABASE = get_env("MYSQL_DATABASE", "rezabots")

# Paths
DATA_DIR = _ROOT / "data"
SESSION_DIR = DATA_DIR / "session"
LOGS_DIR = _ROOT / "logs"
