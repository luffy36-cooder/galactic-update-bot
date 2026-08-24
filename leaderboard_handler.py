# 📁 leaderboard_handler.py

from telegram import Update
from telegram.ext import CallbackContext
from database import read_log_col
import logging
import html

logger = logging.getLogger(__name__)

# 📈 /leaderboard — shows top readers with clickable names (HTML format)
def leaderboard_cmd(update: Update, context: CallbackContext):
    # 🧹 Only count logs that aren't soft-deleted
    pipeline = [
        { "$match": { "deleted": { "$ne": True } } },
        { "$group": { "_id": "$user_id", "chapters_read": { "$sum": 1 } } },
        { "$match": { "chapters_read": { "$gt": 0 } } },
        { "$sort": { "chapters_read": -1 } },
        { "$limit": 10 }
    ]

    leaderboard = list(read_log_col.aggregate(pipeline))
    if not leaderboard:
        update.message.reply_text("No leaderboard data yet~ 💨")
        return

    msg = "🏆 <b>Top Manga Readers</b> 🏆\n\n"

    for i, entry in enumerate(leaderboard, start=1):
        uid = entry['_id']
        chapters = entry['chapters_read']

        try:
            chat = context.bot.get_chat(uid)
            name = chat.full_name or f"User {uid}"
        except:
            name = f"User {uid}"

        # Escape name for HTML and format link
        safe_name = html.escape(name)
        link = f'<a href="tg://user?id={uid}">{safe_name}</a>'
        msg += f"{i}. 👤 {link} — <b>{chapters}</b> chapters read\n"

    update.message.reply_text(msg, parse_mode="HTML")
