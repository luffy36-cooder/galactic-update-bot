# 📁 stats_handler.py

import html
import logging
from telegram import Update
from telegram.ext import CallbackContext
from database import (
    manga_col,
    read_log_col,
    achievements_col,
    channels_col,
    get_manga_by_id,
    is_sudo
)
from config import LOG_CHANNEL_ID, BOT_OWNER_ID

logger = logging.getLogger(__name__)


# 🥇 Top 3 Readers (fast MongoDB aggregation)
def get_top_readers(context: CallbackContext) -> str:
    pipeline = [
        {"$match": {"deleted": {"$ne": True}}},
        {"$group": {"_id": "$user_id", "reads": {"$sum": 1}}},
        {"$sort": {"reads": -1}},
        {"$limit": 3}
    ]
    results = list(read_log_col.aggregate(pipeline))

    if not results:
        return "<i>No reading records yet.</i>"

    medals = ["🥇", "🥈", "🥉"]
    lines = []

    for i, user in enumerate(results):
        user_id = user["_id"]
        reads = user["reads"]
        
        display_name = f"User {user_id}"
        # Try quick cached resolution if available
        try:
            chat = context.bot.get_chat(user_id)
            if chat and chat.full_name:
                display_name = chat.full_name
        except Exception:
            pass

        safe_name = html.escape(display_name)
        lines.append(f"{medals[i]} <a href='tg://user?id={user_id}'>{safe_name}</a> (<b>{reads}</b> reads)")

    return "\n".join(lines)


# 📖 Top Manga by Reads (fast MongoDB aggregation)
def get_top_manga() -> str:
    pipeline = [
        {"$match": {"deleted": {"$ne": True}, "manga_id": {"$exists": True, "$ne": None}}},
        {"$group": {"_id": "$manga_id", "reads": {"$sum": 1}}},
        {"$sort": {"reads": -1}},
        {"$limit": 1}
    ]
    results = list(read_log_col.aggregate(pipeline))

    if not results:
        return "<i>No reads recorded yet</i>"

    top_entry = results[0]
    top_channel_id = top_entry["_id"]
    reads = top_entry["reads"]
    
    manga = get_manga_by_id(top_channel_id)
    name = manga.get("name") if manga else f"Channel {top_channel_id}"

    return f"<b>{html.escape(name)}</b> (<b>{reads}</b> reads)"


# 📊 /stats Command — High-speed, instant response
def stats_cmd(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = user.id

    if not (user_id == BOT_OWNER_ID or is_sudo(user_id)):
        update.message.reply_text("⛔ Only sudo users can access bot stats.")
        return

    # 📦 Ultra-fast DB counts using native MongoDB indexes
    total_manga = manga_col.count_documents({})
    total_channels = channels_col.count_documents({})
    total_users = len(achievements_col.distinct("user_id"))
    total_reads = read_log_col.count_documents({"deleted": {"$ne": True}})

    top_manga_text = get_top_manga()
    top_readers_text = get_top_readers(context)

    stats_message = (
        "📊 <b>Bot Statistics & Overview:</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📚 Total Manga: <b>{total_manga}</b>\n"
        f"📣 Tracked Channels: <b>{total_channels}</b>\n"
        f"👥 Active Readers: <b>{total_users}</b>\n"
        f"📖 Total Chapters Read: <b>{total_reads}</b>\n\n"
        f"🔥 <b>Most Popular Manga:</b>\n{top_manga_text}\n\n"
        f"🏆 <b>Leaderboard Champions:</b>\n{top_readers_text}"
    )

    update.message.reply_text(
        stats_message,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

    # 📝 Log to log channel asynchronously (non-blocking)
    try:
        context.bot.send_message(
            chat_id=LOG_CHANNEL_ID,
            text=(
                f"📊 <b>Stats Accessed</b>\n"
                f"👤 <code>{html.escape(user.full_name)}</code>\n"
                f"🆔 <code>{user_id}</code>"
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Failed to log stats access: {e}")
