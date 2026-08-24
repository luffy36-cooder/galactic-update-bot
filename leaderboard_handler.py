# 📁 leaderboard_handler.py

import html
import logging
from telegram import Update
from telegram.ext import CallbackContext
from database import read_log_col, get_top_rated_manga

logger = logging.getLogger(__name__)


# 📈 /leaderboard — Top readers by chapters read
def leaderboard_cmd(update: Update, context: CallbackContext):
    pipeline = [
        {"$match": {"deleted": {"$ne": True}}},
        {"$group": {"_id": "$user_id", "chapters_read": {"$sum": 1}}},
        {"$match": {"chapters_read": {"$gt": 0}}},
        {"$sort": {"chapters_read": -1}},
        {"$limit": 10}
    ]

    leaderboard = list(read_log_col.aggregate(pipeline))
    if not leaderboard:
        update.message.reply_text("No leaderboard data yet~ 💨")
        return

    msg = "🏆 <b>Top Manga Readers Leaderboard</b> 🏆\n\n"

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for i, entry in enumerate(leaderboard, start=1):
        uid = entry['_id']
        chapters = entry['chapters_read']

        display_name = f"User {uid}"
        try:
            chat = context.bot.get_chat(uid)
            if chat and chat.full_name:
                display_name = chat.full_name
        except Exception:
            pass

        safe_name = html.escape(display_name)
        link = f'<a href="tg://user?id={uid}">{safe_name}</a>'
        medal = medals.get(i, f"<b>{i}.</b>")
        unit = "chapter" if chapters == 1 else "chapters"
        msg += f"{medal} 👤 {link} — <b>{chapters}</b> {unit} read\n"

    update.message.reply_text(msg, parse_mode="HTML", disable_web_page_preview=True)


# ⭐ /toprated — Community highest rated manga
def toprated_cmd(update: Update, context: CallbackContext):
    top_manga = get_top_rated_manga(limit=10)

    if not top_manga:
        update.message.reply_text("⭐ No ratings recorded yet! Rate your favorite manga with <code>/manga &lt;name&gt;</code> or in the Web App.", parse_mode="HTML")
        return

    msg = "🌟 <b>Top Rated Manga Leaderboard</b> 🌟\n"
    msg += "<i>Ranked by community ratings & reviews</i>\n\n"

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for idx, item in enumerate(top_manga, start=1):
        name = html.escape(item["name"])
        link = item["channel_link"]
        rating = item["avg_rating"]
        total = item["total_ratings"]
        medal = medals.get(idx, f"<b>{idx}.</b>")

        msg += f"{medal} <a href='{link}'><b>{name}</b></a>\n"
        msg += f"   ⭐ <b>{rating}/5.0</b> ({total} {'review' if total == 1 else 'reviews'})\n\n"

    update.message.reply_text(msg, parse_mode="HTML", disable_web_page_preview=True)
