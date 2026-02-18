# Rezabots — Admin Telegram Login Manager

Admin-only Telegram bot to manage Telegram account logins across a **main server** and **SSH nodes**. Each account uses its own API_ID/API_HASH (entered in the bot). Sessions are stored on the main server or on the chosen node. V1: login, account list/delete, node management. V2 (later): use accounts for automation.

---

## Prerequisites

- **Python 3.13+**
- **MySQL 8** (or 5.7)
- **Telegram Bot Token** ([@BotFather](https://t.me/BotFather))
- For **nodes**: SSH access (key or password) to remote servers

---

## Quick Start

### 1. Clone and enter project

```bash
cd /path/to/rezabots
```

The app runs from the **`src`** directory; `.env` is read from the **project root** (parent of `src`).

### 2. Virtual environment and dependencies

```bash
cd src
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
# or: pip install python-telegram-bot ">=21" telethon python-dotenv aiomysql asyncssh
```

### 3. MySQL

From **project root** (parent of `src`):

```bash
cd ..   # back to project root
./scripts/install_mysql.sh
```

This installs MySQL (Debian/Ubuntu), creates DB `rezabots`, user `rezabots`, and appends `MYSQL_*` to `.env`. Optional: set `MYSQL_APP_PASSWORD=yourpass` before running to use your own password.

### 4. Environment (`.env`)

Copy the example and edit at **project root**:

```bash
cp .env.example .env
```

Edit `.env`:

| Variable       | Required | Description |
|----------------|----------|-------------|
| `BOT_TOKEN`    | Yes      | From [@BotFather](https://t.me/BotFather) |
| `ADMIN_IDS`    | Yes      | Comma-separated Telegram user IDs (e.g. `123456789`) |
| `MYSQL_*`      | Yes      | Set by `scripts/install_mysql.sh` or manually |

**API_ID / API_HASH** are **not** read from `.env`. Admins enter them **per login** in the bot for each account.

### 5. Run the bot

From **`src`** (so that `core` and `bot` resolve):

```bash
cd src
source .venv/bin/activate
python main.py
```

Or from project root with `PYTHONPATH`:

```bash
PYTHONPATH=src src/.venv/bin/python src/main.py
```

On startup the app: creates `data/session` and `logs`, initialises the DB pool, creates tables and the **main node** if missing, and seeds **admins** from `ADMIN_IDS`. Then it starts polling.

### 6. Use the bot

1. Send **`/admin`** to your bot.
2. If your Telegram user ID is in `ADMIN_IDS`, you get the panel (ورود به اکانت, مدیریت نودها, لیست اکانت‌ها).
3. **Login flow**: ورود به اکانت → choose node → enter **API_ID** → **API_HASH** → phone → code (and 2FA if needed). Sessions are stored on the chosen node (main = local `data/session`, others = path on that server).

### Humantic actions (v1)

Simulate a normal user to reduce ban risk: join channels/chats and send one PM to PV links from `data/links_pool/`, with calm random delays. Runs **per account**, one account after another, reading accounts from DB (main node only in v1).

**Run from `src`:**

```bash
cd src
python -m cli_bots.humantic_actions
```

Flow for each account: **join channels** (random order) → wait → **join chats** (random order) → wait → **send PV** (one message per link). Then the next account. All steps use safe delays (see `cli_bots/humantic_actions/config.py`). Links are read from `data/links_pool/channels.json`, `chats.json`, `pv.json`. Accounts must have `api_id` and `api_hash` set (from login).

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Main Server                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │  Admin Bot   │  │  Core        │  │  MySQL               │   │
│  │  (ptb v21)   │──│  DB, limits, │──│  admins, nodes,       │   │
│  │  Persian UI  │  │  node_runner,│  │  accounts,            │   │
│  │              │  │  telethon_   │  │  login_events         │   │
│  │              │  │  login       │  │                        │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────────────────┘   │
│         │                 │                                      │
│         │                 │  SSH (when node is remote)            │
│         │                 │  Upload scripts/login_worker.py,    │
│         │                 │  run with env API_ID, API_HASH,      │
│         │                 │  bridge stdin (code/2FA) ↔ bot       │
└─────────┼─────────────────┼──────────────────────────────────────┘
          │                 │
          ▼                 ▼
    ┌───────────┐    ┌─────────────────────────────────────────────┐
    │  Admins   │    │  Nodes (optional)                           │
    │  Telegram │    │  SSH server: run Telethon login script,      │
    │  clients  │    │  sessions under node’s session_base_path    │
    └───────────┘    └─────────────────────────────────────────────┘
```

- **Bot**: Entry `/admin`, then menu (ورود به اکانت, مدیریت نودها, لیست اکانت‌ها). All handlers check `admins` table; only whitelisted users proceed.
- **Core**:
  - **db**: MySQL pool, tables, admins/nodes/accounts/login_events, and **rate limits** (3 logins per node per 24h, 4h between logins on same node).
  - **limits**: `can_login_on_node()`, `remaining_logins_today()`.
  - **node_runner**: For **main node** → run Telethon in-process (`telethon_login`). For **other nodes** → SSH, upload `login_worker.py`, run it with user-provided API_ID/API_HASH/phone/session path, bridge code/2FA via stdin.
  - **telethon_login**: Telethon login on main server (code + optional 2FA), using per-account API_ID/API_HASH.
- **Login flow**: Choose node → API_ID → API_HASH → phone → code (and 2FA if needed). Success → insert into `accounts` and `login_events`, store session on main or node.

---

## Project Structure (under `src/`)

| Path | Purpose |
|------|--------|
| `main.py` | Entry: logging, DB init, bootstrap admins, register handlers, `run_polling()` |
| `core/config.py` | Load `.env` from project root; BOT_TOKEN, MYSQL_*, paths |
| `core/db.py` | MySQL pool, tables, CRUD for admins/nodes/accounts/login_events, limit checks |
| `core/limits.py` | Wrappers for login limits per node |
| `core/node_runner.py` | Node health check; run login on main (Telethon) or remote (SSH + worker) |
| `core/telethon_login.py` | Telethon login on main (api_id/api_hash from user) |
| `bot/handlers_admin.py` | `/admin`, بازگشت/انصراف |
| `bot/handlers_login.py` | Conversation: node → API_ID → API_HASH → phone → code → 2FA |
| `bot/handlers_accounts.py` | List accounts, delete (incl. session file on main) |
| `bot/handlers_nodes.py` | List nodes, add node (SSH), delete node |
| `bot/keyboards.py` | Persian reply/inline keyboards |
| `bot/messages.py` | Persian user-facing strings |
| `bot/filters.py` | `ensure_admin(update, context)` |
| `bot/logging_utils.py` | File + stdout logging |
| `scripts/login_worker.py` | Telethon script for **nodes**: reads env (API_ID, API_HASH, phone, session path), stdin = code/2FA, stdout = NEED_CODE/NEED_2FA/OK/ERROR |
| `cli_bots/humantic_actions/` | **Humantic v1**: read accounts from DB (main node), join channels/chats and send PV from `data/links_pool/` with calm delays; run via `python -m cli_bots.humantic_actions` |
| `data/links_pool/` | JSON pools: `channels.json`, `chats.json`, `pv.json` (links used by humantic actions) |

Data at **project root**: `.env`, `data/session/` (main node sessions), `data/links_pool/` (channel/chat/PV links), `logs/` (e.g. `bot_errors.log`).

---

## Limits and Rules

- **3 logins per node per 24 hours** (enforced via `login_events`).
- **4 hours** minimum between two logins on the **same node**.
- One active login conversation per user; wrong code gives a clear message and stays on code step (no brute force).
- UI: Persian, normal reply keyboards; inline only where it helps (e.g. node choice with remaining count).

---

## Useful Tips

### Get your Telegram user ID

Send a message to [@userinfobot](https://t.me/userinfobot) or add a temporary `print(update.effective_user.id)` in the bot and send `/admin`. Put that number in `ADMIN_IDS` in `.env`.

### Create a bot and get BOT_TOKEN

Talk to [@BotFather](https://t.me/BotFather), create a bot, copy the token into `BOT_TOKEN`.

### API_ID and API_HASH (per account)

From [my.telegram.org](https://my.telegram.org): create an application and get API ID and API Hash. **Each account can use a different app**; the admin enters them in the bot when starting a login (after choosing the node).

### Main node vs remote nodes

- **Main node**: Created automatically on first run. Sessions go to `data/session/` on the main server. No SSH.
- **Remote nodes**: Add via “مدیریت نودها” → “افزودن نود جدید”. You need: name, host, port, SSH user, and either **key path** (e.g. `/home/you/.ssh/id_rsa`) or **password**. Session path on node (e.g. `/opt/rezabots/data/session`) must exist or be creatable. The main server uploads `scripts/login_worker.py` and runs it there with env vars; no need to install the full app on the node, only Python 3 + Telethon.

### Running the login worker on a node by hand

For debugging on a node:

```bash
export API_ID=... API_HASH=... TELEGRAM_PHONE=... SESSION_BASE=/path/to/sessions
python3 -u /path/to/login_worker.py
# Then type code and 2FA when it prints NEED_CODE / NEED_2FA
```

### Logs and errors

- **Log file**: under **project root**: `logs/bot_errors.log`. Same output goes to stdout. On startup the app prints the full path (e.g. `Log file: /path/to/rezabots/logs/bot_errors.log`).
- For debugging “ورود به اکانت”: every incoming message is logged at DEBUG (`MSG chat_id=… text=…`), and when the login flow is entered you’ll see `login_entry called text=…`. If you see the MSG line but not `login_entry called`, the entry-point filter didn’t match.
- Errors are logged with full detail; the user only sees a short Persian message.

### Database

- Tables are created on first run (`init_pool()`). To reset: drop DB and run again, or truncate tables (main node row is re-created if `nodes` is empty).
- Main node: `is_main = 1`, `ssh_host`/`ssh_user` NULL, `session_base_path` = main server’s session dir.

### If the bot doesn’t respond to `/admin`

- Check `BOT_TOKEN` and that the process is running.
- Ensure your Telegram user ID is in `ADMIN_IDS` (comma-separated, no spaces if you prefer).
- Check `logs/bot_errors.log` and stdout for exceptions (e.g. DB connection).

### TimedOut / “اتصال به تلگرام برقرار نشد”

If you see `telegram.error.TimedOut` or `httpx.ConnectTimeout` at each step, the server cannot reach Telegram’s API in time (firewall, latency, or blocking).

- The app uses **30s** connect/read/write timeouts and sends a short Persian message to the user on timeout.
- If it still times out: set a **proxy** (e.g. where Telegram is blocked). The library uses `HTTPS_PROXY` or `HTTP_PROXY` from the environment. Example: `export HTTPS_PROXY=http://user:pass@host:port` before running the bot. For SOCKS5, install `python-telegram-bot[socks]` and use `HTTPS_PROXY=socks5://...`.

---

## Summary

| Step | Where | Command / action |
|------|--------|-------------------|
| Deps | `src` | `pip install -e .` (or install deps by hand) |
| MySQL | project root | `./scripts/install_mysql.sh` |
| Env | project root | `cp .env.example .env`, set `BOT_TOKEN`, `ADMIN_IDS` |
| Run | `src` | `python main.py` (with venv activated) |
| Use | Telegram | Send `/admin`, then use the Persian menu |

API_ID and API_HASH are **always entered in the bot** for each login, not taken from `.env`.




---
## Local Dev

```bash
export PYTHONPATH="/home/mahdi/Projects/rezabots/src:$PYTHONPATH"
```