"""Async MySQL connection and table setup."""
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Any

import aiomysql

from .config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE

logger = logging.getLogger(__name__)

# Pool created at app start, closed at shutdown
_pool: aiomysql.Pool | None = None


async def init_pool() -> None:
    global _pool
    if _pool is not None:
        return
    _pool = await aiomysql.create_pool(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        db=MYSQL_DATABASE,
        minsize=1,
        maxsize=5,
        autocommit=True,
    )
    logger.info("MySQL pool created")
    await _ensure_tables()


async def close_pool() -> None:
    global _pool
    if _pool:
        _pool.close()
        await _pool.wait_closed()
        _pool = None
        logger.info("MySQL pool closed")


@asynccontextmanager
async def get_conn() -> AsyncIterator[aiomysql.Connection]:
    if _pool is None:
        raise RuntimeError("DB pool not initialized")
    async with _pool.acquire() as conn:
        yield conn


async def _ensure_tables() -> None:
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    telegram_user_id BIGINT NOT NULL UNIQUE,
                    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6)
                )
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS nodes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    is_main TINYINT(1) NOT NULL DEFAULT 0,
                    ssh_host VARCHAR(255) NULL,
                    ssh_port INT NOT NULL DEFAULT 22,
                    ssh_user VARCHAR(255) NULL,
                    ssh_key_path VARCHAR(512) NULL,
                    ssh_password VARCHAR(512) NULL,
                    session_base_path VARCHAR(512) NOT NULL,
                    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6)
                )
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    node_id INT NOT NULL,
                    phone VARCHAR(32) NOT NULL,
                    session_path VARCHAR(512) NOT NULL,
                    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
                    last_used_at DATETIME(6) NULL,
                    UNIQUE KEY uq_node_phone (node_id, phone),
                    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
                )
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS login_events (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    node_id INT NOT NULL,
                    completed_at DATETIME(6) NOT NULL,
                    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
                )
            """)
    logger.info("Tables ensured")
    await ensure_main_node_if_empty()


async def ensure_main_node_if_empty() -> None:
    from .config import SESSION_DIR
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1 FROM nodes LIMIT 1")
            if await cur.fetchone():
                return
            session_path = str(SESSION_DIR)
            await cur.execute(
                """INSERT INTO nodes (name, is_main, ssh_host, ssh_port, ssh_user, session_base_path)
                   VALUES (%s, 1, NULL, 22, NULL, %s)""",
                ("نود اصلی", session_path),
            )
    logger.info("Main node created")

# --- Admins ---

async def is_admin(telegram_user_id: int) -> bool:
    async with get_conn() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT 1 FROM admins WHERE telegram_user_id = %s LIMIT 1",
                (telegram_user_id,),
            )
            row = await cur.fetchone()
            return row is not None


async def ensure_admin(telegram_user_id: int) -> None:
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT IGNORE INTO admins (telegram_user_id) VALUES (%s)",
                (telegram_user_id,),
            )


async def bootstrap_admins_from_env() -> None:
    from .config import ADMIN_IDS_STR
    if not ADMIN_IDS_STR:
        return
    for s in ADMIN_IDS_STR.split(","):
        s = s.strip()
        if not s:
            continue
        try:
            uid = int(s)
            await ensure_admin(uid)
        except ValueError:
            continue


# --- Nodes ---

async def get_main_node_id() -> int | None:
    async with get_conn() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id FROM nodes WHERE is_main = 1 LIMIT 1")
            row = await cur.fetchone()
            return row["id"] if row else None


async def get_node(node_id: int) -> dict[str, Any] | None:
    async with get_conn() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT * FROM nodes WHERE id = %s",
                (node_id,),
            )
            return await cur.fetchone()


async def list_nodes() -> list[dict[str, Any]]:
    async with get_conn() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT * FROM nodes ORDER BY is_main DESC, id ASC"
            )
            return await cur.fetchall()


async def create_node(
    name: str,
    is_main: bool,
    session_base_path: str,
    ssh_host: str | None = None,
    ssh_port: int = 22,
    ssh_user: str | None = None,
    ssh_key_path: str | None = None,
    ssh_password: str | None = None,
) -> int:
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO nodes (name, is_main, ssh_host, ssh_port, ssh_user, ssh_key_path, ssh_password, session_base_path)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (name, 1 if is_main else 0, ssh_host, ssh_port, ssh_user, ssh_key_path, ssh_password, session_base_path),
            )
            return cur.lastrowid


async def delete_node(node_id: int) -> None:
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM nodes WHERE id = %s", (node_id,))


# --- Login events (for limits) ---

LOGINS_PER_NODE_PER_24H = 3
BREATH_HOURS = 4


async def count_logins_last_24h(node_id: int) -> int:
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """SELECT COUNT(*) AS c FROM login_events
                   WHERE node_id = %s AND completed_at >= NOW() - INTERVAL 24 HOUR""",
                (node_id,),
            )
            row = await cur.fetchone()
            return row[0] if row else 0


async def last_login_at(node_id: int) -> str | None:
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """SELECT MAX(completed_at) AS t FROM login_events WHERE node_id = %s""",
                (node_id,),
            )
            row = await cur.fetchone()
            return str(row[0]) if row and row[0] else None


async def can_login_on_node(node_id: int) -> tuple[bool, str]:
    """Returns (allowed, reason_in_persian)."""
    count = await count_logins_last_24h(node_id)
    if count >= LOGINS_PER_NODE_PER_24H:
        return False, f"در ۲۴ ساعت گذشته روی این نود حداکثر {LOGINS_PER_NODE_PER_24H} ورود انجام شده. فردا دوباره امتحان کنید."
    last = await last_login_at(node_id)
    if last:
        async with get_conn() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT TIMESTAMPDIFF(SECOND, %s, NOW()) AS diff",
                    (last,),
                )
                row = await cur.fetchone()
                diff_sec = row[0] if row else 0
        if diff_sec < BREATH_HOURS * 3600:
            remain = (BREATH_HOURS * 3600 - diff_sec) // 60
            return False, f"بین دو ورود روی یک نود باید حداقل {BREATH_HOURS} ساعت فاصله باشد. حدود {remain} دقیقه دیگر مجاز است."
    return True, ""


async def record_login_event(node_id: int) -> None:
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO login_events (node_id, completed_at) VALUES (%s, NOW(6))",
                (node_id,),
            )


# --- Accounts ---

async def create_account(node_id: int, phone: str, session_path: str) -> int:
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO accounts (node_id, phone, session_path) VALUES (%s, %s, %s)",
                (node_id, phone, session_path),
            )
            return cur.lastrowid


async def list_accounts(node_id: int | None = None) -> list[dict[str, Any]]:
    async with get_conn() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            if node_id is not None:
                await cur.execute(
                    "SELECT a.*, n.name AS node_name FROM accounts a JOIN nodes n ON a.node_id = n.id WHERE a.node_id = %s ORDER BY a.id",
                    (node_id,),
                )
            else:
                await cur.execute(
                    "SELECT a.*, n.name AS node_name FROM accounts a JOIN nodes n ON a.node_id = n.id ORDER BY a.node_id, a.id",
                )
            return await cur.fetchall()


async def get_account_by_phone(phone: str, node_id: int | None = None) -> dict[str, Any] | None:
    async with get_conn() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            phone_clean = "".join(c for c in phone if c.isdigit())
            if node_id is not None:
                await cur.execute(
                    "SELECT a.*, n.name AS node_name FROM accounts a JOIN nodes n ON a.node_id = n.id WHERE a.phone = %s AND a.node_id = %s",
                    (phone_clean or phone, node_id),
                )
            else:
                await cur.execute(
                    "SELECT a.*, n.name AS node_name FROM accounts a JOIN nodes n ON a.node_id = n.id WHERE a.phone = %s",
                    (phone_clean or phone,),
                )
            return await cur.fetchone()


async def delete_account(account_id: int) -> None:
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM accounts WHERE id = %s", (account_id,))


async def get_account(account_id: int) -> dict[str, Any] | None:
    async with get_conn() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT a.*, n.name AS node_name FROM accounts a JOIN nodes n ON a.node_id = n.id WHERE a.id = %s",
                (account_id,),
            )
            return await cur.fetchone()
