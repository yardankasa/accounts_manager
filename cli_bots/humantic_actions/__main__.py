"""
Run humantic actions from CLI:
  python -m cli_bots.humantic_actions
Must be run from project root (where main.py and core/ live).
"""
import sys
from pathlib import Path

# Ensure project root is on path
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from .runner import main_sync

if __name__ == "__main__":
    main_sync()
