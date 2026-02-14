"""Login limits: 3 per node per 24h, 4h breath between logins."""
from . import db

async def can_login_on_node(node_id: int) -> tuple[bool, str]:
    return await db.can_login_on_node(node_id)


async def remaining_logins_today(node_id: int) -> int:
    used = await db.count_logins_last_24h(node_id)
    return max(0, db.LOGINS_PER_NODE_PER_24H - used)
