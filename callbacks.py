import logging
import random
import html
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import CallbackContext

from database import (
    update_manga_status,
    get_user_manga_lists,
    get_manga_by_id,
    mark_chapter_as_read,
    read_log_col
)
from config import LOG_CHANNEL_ID

logger = logging.getLogger(__name__)


def log_to_channel(context: CallbackContext, text: str):
    try:
        context.bot.send_message(chat_id=LOG_CHANNEL_ID, text=text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        logger.warning(f"⚠️ Failed to log to channel: {e}")


def format_manga_list(channel_ids):
    if not channel_ids:
        return "<i>None yet 🥺</i>"
    lines = []
    for cid in channel_ids:
        info = get_manga_by_id(cid)
        if info:
            name = html.escape(info.get("name", "Unknown"))
            link = info.get("channel_link") or f"https://t.me/c/{str(cid)[4:]}/1"
            lines.append(f"• <a href='{link}'>{name}</a>")
        else:
            lines.append(f"• Channel {cid}")
    return "\n".join(lines)


# 🌟 Main inline callback button handler
def handle_status_buttons(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    # Handle view_mylist
    if data.startswith("view_mylist:"):
        try:
            _, target_id = data.split(":", 1)
            if str(user_id) != target_id:
                query.answer("🚫 That’s not your list, senpai 👀", show_alert=True)
                return

            lists = get_user_manga_lists(user_id)
            text = (
                "📚 <b>Your Manga List Summary</b>\n\n"
                f"📖 <b>Read:</b>\n{format_manga_list(lists.get('read', []))}\n\n"
                f"❤️ <b>Favorites:</b>\n{format_manga_list(lists.get('favorite', []))}\n\n"
                f"🏁 <b>Completed:</b>\n{format_manga_list(lists.get('completed', []))}\n\n"
                f"👋 <b>Dropped:</b>\n{format_manga_list(lists.get('dropped', []))}\n\n"
                f"⏸️ <b>On Hold:</b>\n{format_manga_list(lists.get('hold', []))}"
            )
            query.message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)
            query.answer()
        except Exception as e:
            logger.error(f"⚠️ Failed to handle view_mylist: {e}")
            query.answer("⚠️ Something went wrong.", show_alert=True)
        return

    # Parse status callbacks e.g. read_-100123456_99999
    parts = data.split("_")
    if len(parts) < 3:
        query.answer("⚠️ Invalid button data.", show_alert=True)
        return

    action = parts[0]
    try:
        channel_id = int(parts[1])
        owner_id = int(parts[2])
    except ValueError:
        query.answer("⚠️ Corrupted button data.", show_alert=True)
        return

    if user_id != owner_id:
        roasts = [
            "👀 This ain't your manga, back off.",
            "😫 Hands off, imposter!",
            "😼 Get your own list, side character!"
        ]
        try:
            query.answer(random.choice(roasts), show_alert=True)
        except Exception:
            pass
        return

    status_map = {
        "read": "read", "unread": "read",
        "fav": "favorite", "unfav": "favorite",
        "complete": "completed", "uncomplete": "completed",
        "drop": "dropped", "undrop": "dropped",
        "hold": "hold", "unhold": "hold",
    }

    if action not in status_map:
        query.answer("⚠️ Unknown action.", show_alert=True)
        return

    status = status_map[action]
    add = not action.startswith("un")
    update_manga_status(user_id, channel_id, status, add=add)

    # Reading logs tracking
    if status == "read" and add:
        mark_chapter_as_read(user_id, channel_id, chapter_number=0)
    elif status == "read" and not add:
        read_log_col.update_one(
            {"user_id": user_id, "chapter": f"{channel_id}_0", "deleted": {"$ne": True}},
            {"$set": {"deleted": True}}
        )

    feedback = {
        "read": "✅ Marked as Read!",
        "unread": "❌ Removed from Read list!",
        "fav": "❤️ Added to Favorites!",
        "unfav": "💔 Removed from Favorites!",
        "complete": "🏁 Marked as Completed!",
        "uncomplete": "⛔ Removed from Completed list!",
        "drop": "👋 Dropped!",
        "undrop": "♻️ Restored from Dropped!",
        "hold": "⏸️ Put on Hold!",
        "unhold": "✅ Removed from Hold!",
    }

    try:
        query.answer(text=feedback.get(action, "Updated!"), show_alert=False)
    except Exception:
        pass


# 🔘 Multiple Search Result Selection Callback
def select_manga_callback(update: Update, context: CallbackContext):
    from manga_search import _send_single_manga

    query = update.callback_query
    query.answer()

    data = query.data
    if data.startswith("select_"):
        parts = data.split("_")
        if len(parts) < 3:
            return

        try:
            channel_id = int(parts[1])
            owner_id = int(parts[2])
        except ValueError:
            return

        if owner_id != query.from_user.id:
            query.answer("This search menu belongs to someone else!", show_alert=True)
            return

        manga = get_manga_by_id(channel_id)
        if not manga:
            query.edit_message_text("⚠️ Manga not found.")
            return

        _send_single_manga(update, manga)
