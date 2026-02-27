"""Server status dashboard for the current node (single-server mode)."""

import logging
import os
import platform
import shutil
from datetime import datetime, timezone

import psutil
from telegram import Update
from telegram.ext import ContextTypes

import core.db as db
from .filters import ensure_admin
from .keyboards import main_admin_keyboard

logger = logging.getLogger(__name__)


async def nodes_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show status for the current server (CPU, RAM, disk, accounts, logins)."""
    if not await ensure_admin(update, context):
        return

    # System metrics
    try:
        load1, load5, load15 = psutil.getloadavg()
    except (AttributeError, OSError):
        load1 = load5 = load15 = 0.0

    cpu_percent = psutil.cpu_percent(interval=0.3)
    mem = psutil.virtual_memory()
    disk = shutil.disk_usage("/")

    # App-level metrics
    main_node_id = await db.get_main_node_id()
    accs = await db.list_accounts(node_id=main_node_id) if main_node_id is not None else []
    acc_count = len(accs)

    logins_24h = 0
    last_login = None
    if main_node_id is not None:
        logins_24h = await db.count_logins_last_24h(main_node_id)
        last_login = await db.last_login_at(main_node_id)

    hostname = platform.node() or os.uname().nodename
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    text = (
        "🖥 وضعیت سرور فعلی (نود اصلی)\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 میزبان: {hostname}\n"
        f"🕒 زمان: {now}\n\n"
        f"💻 Load average (۱/۵/۱۵ دقیقه): {load1:.2f} / {load5:.2f} / {load15:.2f}\n"
        f"⚙️ CPU usage: {cpu_percent:.1f}%\n"
        f"🧠 RAM: {mem.used // (1024**2)}MB / {mem.total // (1024**2)}MB ({mem.percent:.1f}%)\n"
        f"💾 Disk (/): {disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB\n\n"
        f"📊 تعداد اکانت‌های ثبت‌شده: {acc_count}\n"
        f"🔑 ورودهای ۲۴ ساعت گذشته: {logins_24h}\n"
        f"⏱ آخرین زمان ورود موفق: {last_login or '—'}\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

    await update.message.reply_text(text, reply_markup=main_admin_keyboard())
