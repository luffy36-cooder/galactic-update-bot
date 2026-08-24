# 📁 recommend_handler.py

import html
import random
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext
from database import (
    manga_col,
    read_log_col,
    get_user_manga_lists,
    get_user_bookmarks,
    get_manga_by_id
)


# 🧠 /recommend — Smart suggestion based on unread & popular manga
def recommend_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    # 1. Collect all manga the user has already interacted with
    user_lists = get_user_manga_lists(user_id)
    user_bookmarks = get_user_bookmarks(user_id)

    interacted_channel_ids = set(user_lists.get("read", [])) | \
                             set(user_lists.get("completed", [])) | \
                             set(user_lists.get("dropped", []))

    for bm in user_bookmarks:
        cid = bm.get("channel_id")
        if cid:
            interacted_channel_ids.add(cid)

    # 2. Get top trending/popular manga from read logs
    pipeline = [
        {"$match": {"deleted": {"$ne": True}, "manga_id": {"$exists": True, "$ne": None}}},
        {"$group": {"_id": "$manga_id", "reads": {"$sum": 1}}},
        {"$sort": {"reads": -1}},
        {"$limit": 20}
    ]
    popular_entries = list(read_log_col.aggregate(pipeline))
    popular_channel_ids = [entry["_id"] for entry in popular_entries]

    # 3. Filter unread popular manga
    recommended_channel_ids = [cid for cid in popular_channel_ids if cid not in interacted_channel_ids]

    # If we need more recommendations, sample from general catalog
    if len(recommended_channel_ids) < 5:
        all_catalog = list(manga_col.find({}, {"channel_id": 1, "name": 1, "channel_link": 1}))
        catalog_unread = [m["channel_id"] for m in all_catalog if m.get("channel_id") and m["channel_id"] not in interacted_channel_ids and m["channel_id"] not in recommended_channel_ids]
        random.shuffle(catalog_unread)
        recommended_channel_ids.extend(catalog_unread[: (5 - len(recommended_channel_ids))])

    if not recommended_channel_ids:
        update.message.reply_text(
            "🌟 You've caught up with all registered manga! Check back soon for new additions.",
            parse_mode="HTML"
        )
        return

    # 4. Build recommendations list
    selected_ids = recommended_channel_ids[:5]
    lines = []
    buttons = []

    for cid in selected_ids:
        manga = get_manga_by_id(cid)
        if not manga:
            continue

        name = html.escape(manga.get("name", "Unknown"))
        link = manga.get("channel_link") or f"https://t.me/c/{str(cid)[4:]}/1"
        total = manga.get("total_chapters")
        chap_info = f" ({total} chapters)" if total else ""

        lines.append(f"• <a href='{link}'><b>{name}</b></a>{chap_info}")
        buttons.append([InlineKeyboardButton(f"📖 {manga.get('name', 'Read')[:30]}", url=link)])

    reply_text = (
        "✨ <b>Handpicked Manga Recommendations For You:</b>\n\n"
        + "\n".join(lines)
        + "\n\n<i>Tap a title to start reading!</i>"
    )

    update.message.reply_text(
        reply_text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
    )
