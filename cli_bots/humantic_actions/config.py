"""
Humantic actions config: calm delays and paths for v1.
All times in seconds. Kept safe to avoid Telegram limits.
"""
import sys
from pathlib import Path

# Ensure app root is on path so we can import core
_APP_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from core.config import DATA_DIR

# Links pool: channels.json, chats.json, pv.json
LINKS_POOL_DIR = DATA_DIR / "links_pool"

# Resume state: if script crashes, next run continues from here (no re-join / no duplicate PV).
# State is only used when it's from a recent run (see RESUME_MAX_AGE_SECONDS).
STATE_FILE = DATA_DIR / "humantic_state.json"
# Consider state "stale" after this many seconds; then we start a fresh run.
RESUME_MAX_AGE_SECONDS = 2 * 3600  # 2 hours

# Calm delays (seconds) — v1: safe and slow
DELAY_BETWEEN_JOINS_MIN = 15
DELAY_BETWEEN_JOINS_MAX = 45
DELAY_BETWEEN_STEPS_MIN = 30
DELAY_BETWEEN_STEPS_MAX = 90

# Default first message when opening a PV (private chat)
PV_DEFAULT_MESSAGE = "سلام"
