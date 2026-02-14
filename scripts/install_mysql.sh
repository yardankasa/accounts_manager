#!/usr/bin/env bash
# Install MySQL, create database and user, write .env (Debian/Ubuntu).
# Run from project root: ./scripts/install_mysql.sh
# Optional: MYSQL_APP_PASSWORD=yourpass (otherwise generated)

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

MYSQL_DB="${MYSQL_DATABASE:-rezabots}"
MYSQL_APP_USER="${MYSQL_USER:-rezabots}"
MYSQL_APP_PASSWORD="${MYSQL_APP_PASSWORD:-}"

# Install MySQL server if not present (Debian/Ubuntu)
if ! command -v mysql &>/dev/null; then
  echo "Installing MySQL server..."
  export DEBIAN_FRONTEND=noninteractive
  sudo apt-get update -qq
  sudo apt-get install -y -qq mysql-server
fi

# Start MySQL if not running
if ! sudo service mysql status 2>/dev/null | grep -q "running"; then
  sudo service mysql start 2>/dev/null || true
fi

# Generate password if not provided
if [ -z "$MYSQL_APP_PASSWORD" ]; then
  MYSQL_APP_PASSWORD="$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 24)"
  echo "Generated MySQL password for $MYSQL_APP_USER (save it): $MYSQL_APP_PASSWORD"
fi

# Create database and user (idempotent)
sudo mysql -e "
  CREATE DATABASE IF NOT EXISTS \`$MYSQL_DB\`;
  CREATE USER IF NOT EXISTS '$MYSQL_APP_USER'@'localhost' IDENTIFIED BY '$MYSQL_APP_PASSWORD';
  GRANT ALL PRIVILEGES ON \`$MYSQL_DB\`.* TO '$MYSQL_APP_USER'@'localhost';
  FLUSH PRIVILEGES;
" 2>/dev/null || {
  echo "If CREATE USER failed (MySQL 8): DROP USER IF EXISTS '$MYSQL_APP_USER'@'localhost'; then run again."
  sudo mysql -e "CREATE USER IF NOT EXISTS '$MYSQL_APP_USER'@'localhost' IDENTIFIED BY '$MYSQL_APP_PASSWORD'; GRANT ALL ON \`$MYSQL_DB\`.* TO '$MYSQL_APP_USER'@'localhost'; FLUSH PRIVILEGES;"
}

# Write .env (update MYSQL_* or append)
ENV_FILE="$PROJECT_ROOT/.env"
TEMP_ENV=$(mktemp)
if [ -f "$ENV_FILE" ]; then
  grep -v '^MYSQL_HOST=\|^MYSQL_PORT=\|^MYSQL_USER=\|^MYSQL_PASSWORD=\|^MYSQL_DATABASE=' "$ENV_FILE" > "$TEMP_ENV" || true
else
  touch "$TEMP_ENV"
fi
{
  echo "MYSQL_HOST=127.0.0.1"
  echo "MYSQL_PORT=3306"
  echo "MYSQL_USER=$MYSQL_APP_USER"
  echo "MYSQL_PASSWORD=$MYSQL_APP_PASSWORD"
  echo "MYSQL_DATABASE=$MYSQL_DB"
} >> "$TEMP_ENV"
mv "$TEMP_ENV" "$ENV_FILE"
echo "Wrote MYSQL_* to $ENV_FILE"
