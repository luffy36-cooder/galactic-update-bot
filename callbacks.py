import logging
import random
import html
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import CallbackContext

from database import (
    update_manga_status,
    get_user_manga_lists,
    get_manga_by_id,
    mark_chapter_as_read,
    read_log_col,
    save_manga_rating,
    get_manga_rating_summary,
    subscribe_manga,
    unsubscribe_manga,
    is_user_subscribed,
    get_user_bookmarks,
    get_user_badges
)
from config import LOG_CHANNEL_ID, WEB_APP_URL

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
    from manga_search import _send_single_manga

    query = update.callback_query
    user_id = query.from_user.id
    user_name = query.from_user.full_name or "Reader"
    data = query.data

    # 1. Handle view_mylist
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

    # 1b. Handle Hub Shelves (hub_shelf:<shelf>:<target_id>)
    if data.startswith("hub_shelf:"):
        try:
            parts = data.split(":")
            if len(parts) >= 3:
                shelf = parts[1]
                target_id = parts[2]
                if str(user_id) != target_id:
                    query.answer("👀 You can only view your own hub!", show_alert=True)
                    return

                lists = get_user_manga_lists(user_id)
                shelf_map = {
                    "read": ("Read Shelf", "📖"),
                    "favorite": ("Favorites", "❤️"),
                    "completed": ("Completed List", "🏁"),
                    "hold": ("On Hold Shelf", "⏸️"),
                    "dropped": ("Dropped Shelf", "👋")
                }
                name, emoji = shelf_map.get(shelf, ("Shelf", "📚"))
                items = lists.get(shelf, [])

                text = f"{emoji} <b>Your {name} ({len(items)}):</b>\n\n{format_manga_list(items)}"
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back to Hub", callback_data=f"hub_back:{user_id}")]
                ])
                query.edit_message_text(text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
                query.answer()
        except Exception as e:
            logger.error(f"Error handling hub_shelf: {e}")
        return

    # 1c. Handle Return to Hub (hub_back:<target_id>)
    if data.startswith("hub_back:"):
        try:
            lists = get_user_manga_lists(user_id)
            bookmarks = get_user_bookmarks(user_id)
            badges = get_user_badges(user_id)

            read_count = len(lists.get("read", []))
            fav_count = len(lists.get("favorite", []))
            comp_count = len(lists.get("completed", []))
            hold_count = len(lists.get("hold", []))
            drop_count = len(lists.get("dropped", []))
            bm_count = len(bookmarks)
            badge_str = " ".join(badges) if badges else "🎖️ Explorer"

            text = (
                f"🛸 <b>Personal Manga Hub</b> 🌌\n\n"
                f"👤 <b>Reader:</b> {html.escape(user_name)}\n"
                f"🏅 <b>Badges:</b> {badge_str}\n\n"
                f"📊 <b>Your Reading Shelves:</b>\n"
                f"• 📖 Read: <b>{read_count}</b> titles\n"
                f"• ❤️ Favorites: <b>{fav_count}</b> titles\n"
                f"• 🏁 Completed: <b>{comp_count}</b> titles\n"
                f"• ⏸️ On Hold: <b>{hold_count}</b> titles\n"
                f"• 👋 Dropped: <b>{drop_count}</b> titles\n"
                f"• 📌 Bookmarks: <b>{bm_count}</b> chapters\n\n"
                f"<i>Tap any shelf below to view your manga:</i>"
            )

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(f"📖 Read ({read_count})", callback_data=f"hub_shelf:read:{user_id}"),
                    InlineKeyboardButton(f"❤️ Favorites ({fav_count})", callback_data=f"hub_shelf:favorite:{user_id}")
                ],
                [
                    InlineKeyboardButton(f"🏁 Completed ({comp_count})", callback_data=f"hub_shelf:completed:{user_id}"),
                    InlineKeyboardButton(f"⏸️ On Hold ({hold_count})", callback_data=f"hub_shelf:hold:{user_id}")
                ],
                [
                    InlineKeyboardButton(f"👋 Dropped ({drop_count})", callback_data=f"hub_shelf:dropped:{user_id}"),
                    InlineKeyboardButton(f"📌 Bookmarks ({bm_count})", callback_data="bm_list_0")
                ],
                [
                    InlineKeyboardButton("👤 Visual Web Profile", web_app=WebAppInfo(url=f"{WEB_APP_URL}/profile?user_id={user_id}")),
                    InlineKeyboardButton("🔍 Search Manga", switch_inline_query_current_chat="")
                ]
            ])
            query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
            query.answer()
        except Exception as e:
            logger.error(f"Error handling hub_back: {e}")
        return

    # 2. Handle Rating Menu: showrate_<channel_id>_<owner_id>
    if data.startswith("showrate_"):
        parts = data.split("_")
        if len(parts) >= 3:
            try:
                cid = int(parts[1])
                owner_id = int(parts[2])
            except ValueError:
                return

            if user_id != owner_id:
                query.answer("👀 You can only rate from your own search!", show_alert=True)
                return

            rate_buttons = [
                [
                    InlineKeyboardButton("⭐ 1", callback_data=f"setrate_{cid}_1_{user_id}"),
                    InlineKeyboardButton("⭐ 2", callback_data=f"setrate_{cid}_2_{user_id}"),
                    InlineKeyboardButton("⭐ 3", callback_data=f"setrate_{cid}_3_{user_id}"),
                    InlineKeyboardButton("⭐ 4", callback_data=f"setrate_{cid}_4_{user_id}"),
                    InlineKeyboardButton("⭐ 5", callback_data=f"setrate_{cid}_5_{user_id}")
                ],
                [InlineKeyboardButton("⬅ Back to Manga", callback_data=f"select_{cid}_{user_id}")]
            ]
            try:
                query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(rate_buttons))
                query.answer("Select your rating (1 to 5 stars):")
            except Exception:
                pass
            return

    # 3. Handle Rating Save: setrate_<channel_id>_<rating>_<owner_id>
    if data.startswith("setrate_"):
        parts = data.split("_")
        if len(parts) >= 4:
            try:
                cid = int(parts[1])
                rating = int(parts[2])
                owner_id = int(parts[3])
            except ValueError:
                return

            if user_id != owner_id:
                query.answer("👀 This isn't your rating menu.", show_alert=True)
                return

            save_manga_rating(user_id, user_name, cid, rating)
            manga = get_manga_by_id(cid)
            manga_name = manga.get("name", "Manga") if manga else "Manga"
            query.answer(f"⭐ You rated {manga_name} {rating}/5 stars! Thank you! 🎉", show_alert=True)

            if manga:
                _send_single_manga(update, manga)
            return

    # 4. Handle Subscription Toggle: subtoggle_<channel_id>_<owner_id>
    if data.startswith("subtoggle_"):
        parts = data.split("_")
        if len(parts) >= 3:
            try:
                cid = int(parts[1])
                owner_id = int(parts[2])
            except ValueError:
                return

            if user_id != owner_id:
                query.answer("👀 This button is not for you.", show_alert=True)
                return

            currently_subbed = is_user_subscribed(user_id, cid)
            if currently_subbed:
                unsubscribe_manga(user_id, cid)
                query.answer("🔕 Unsubscribed from chapter release alerts.", show_alert=True)
            else:
                subscribe_manga(user_id, cid)
                query.answer("🔔 Subscribed! You will receive direct DM alerts when new chapters drop! 🚀", show_alert=True)

            manga = get_manga_by_id(cid)
            if manga:
                _send_single_manga(update, manga)
            return

    # 5. Handle standard status callbacks e.g. read_-100123456_99999
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

    # Refresh card display in-place
    manga = get_manga_by_id(channel_id)
    if manga:
        _send_single_manga(update, manga)


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
