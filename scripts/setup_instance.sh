#!/usr/bin/env bash
# Simple helper to bootstrap a Rezabots instance on this server.
# Usage (from project root): ./scripts/setup_instance.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC_DIR="$PROJECT_ROOT/src"

cd "$PROJECT_ROOT"

echo "==> Creating virtualenv (if missing)..."
python3 -m venv "$SRC_DIR/.venv"
source "$SRC_DIR/.venv/bin/activate"

echo "==> Installing Rezabots in editable mode..."
pip install --upgrade pip
pip install -e "$SRC_DIR"

echo "==> Copying .env.example to src/.env if missing..."
if [ ! -f "$SRC_DIR/.env" ]; then
  if [ -f "$SRC_DIR/.env.example" ]; then
    cp "$SRC_DIR/.env.example" "$SRC_DIR/.env"
    echo "   Edit $SRC_DIR/.env and set BOT_TOKEN, ADMIN_IDS and MYSQL_* before running the bot."
  else
    echo "   WARNING: .env.example not found. Create $SRC_DIR/.env manually."
  fi
else
  echo "   $SRC_DIR/.env already exists; leaving it as-is."
fi

echo ""
echo "Done."
echo "To run the bot on this server:"
echo "  cd \"$SRC_DIR\""
echo "  source .venv/bin/activate"
echo "  python main.py"

