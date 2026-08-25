import html
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import CallbackContext
from database import (
    get_user_profile,
    get_user_badges,
    get_user_manga_lists,
    get_user_subscriptions
)
from config import WEB_APP_URL

logger = logging.getLogger(__name__)

# ⭐ Rank system
def get_rank_title(read_count: int) -> str:
    if read_count >= 50:
        return "📚 Elite Grandmaster Reader"
    elif read_count >= 25:
        return "🌟🌟🌟🌟 Master Reader"
    elif read_count >= 15:
        return "🌟🌟🌟 Senior Reader"
    elif read_count >= 10:
        return "🌟🌟 Intermediate Reader"
    elif read_count >= 1:
        return "🌟 Novice Reader"
    return "📥 Newbie Explorer"


# 🖼️ /profile command (with user-bound inline buttons)
def profile_cmd(update: Update, context: CallbackContext):
    user = update.effective_user
    if not user:
        return
    user_id = user.id

    try:
        # DB Fetch
        profile = get_user_profile(user_id)
        badges = get_user_badges(user_id)
        manga_lists = get_user_manga_lists(user_id)
        subs = get_user_subscriptions(user_id)

        # Count values
        bookmark_count = profile.get("bookmarks", 0)
        read_count = len(manga_lists.get("read", []))
        completed_count = len(manga_lists.get("completed", []))
        fav_count = len(manga_lists.get("favorite", []))
        drop_count = len(manga_lists.get("dropped", []))
        hold_count = len(manga_lists.get("hold", []))
        sub_count = len(subs)
        rank = get_rank_title(read_count)

        badge_display = " ".join(badges) if badges else "🎖️ Explorer"
        safe_name = html.escape(user.full_name or "Unknown")
        safe_username = f"@{html.escape(user.username)}" if user.username else "N/A"

        # Caption
        caption = (
            f"👤 <b>Reader Profile — Cosmic Hub</b>\n\n"
            f"• <b>Name:</b> {safe_name}\n"
            f"• <b>Username:</b> {safe_username}\n"
            f"• <b>User ID:</b> <code>{user_id}</code>\n\n"
            f"📊 <b>Reading Progress:</b>\n"
            f"• 🔔 <b>Subscribed Alerts:</b> {sub_count} titles\n"
            f"• 📌 <b>Bookmarks:</b> {bookmark_count} chapters\n"
            f"• 📖 <b>Read:</b> {read_count}  |  🏁 <b>Completed:</b> {completed_count}\n"
            f"• ❤️ <b>Favorites:</b> {fav_count}  |  ⏸️ <b>Hold:</b> {hold_count}\n"
            f"• 👋 <b>Dropped:</b> {drop_count}\n\n"
            f"🏅 <b>Rank:</b> {rank}\n"
            f"🎖️ <b>Badges:</b> {badge_display}"
        )

        # Inline buttons
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🛸 My Hub", callback_data=f"hub_back:{user_id}"),
                InlineKeyboardButton("👤 Web Profile", web_app=WebAppInfo(url=f"{WEB_APP_URL}/webprofile"))
            ],
            [
                InlineKeyboardButton("📜 View My Lists", callback_data=f"view_mylist:{user_id}"),
                InlineKeyboardButton(f"📌 Bookmarks ({bookmark_count})", callback_data=f"bm_list_{user_id}")
            ],
            [
                InlineKeyboardButton("🔍 Search Manga", switch_inline_query_current_chat="")
            ]
        ])

        msg = update.effective_message or update.message
        photo_sent = False

        # Try sending profile pic if available
        try:
            if update.effective_chat:
                context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_photo")
            photos = context.bot.get_user_profile_photos(user_id, limit=1)
            if photos and photos.total_count > 0:
                if msg:
                    msg.reply_photo(
                        photo=photos.photos[0][0].file_id,
                        caption=caption,
                        parse_mode="HTML",
                        reply_markup=keyboard
                    )
                    photo_sent = True
                elif update.effective_chat:
                    context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=photos.photos[0][0].file_id,
                        caption=caption,
                        parse_mode="HTML",
                        reply_markup=keyboard
                    )
                    photo_sent = True
        except Exception as e:
            logger.debug(f"Profile photo send skipped: {e}")

        # Fallback to text message
        if not photo_sent:
            if msg:
                msg.reply_text(
                    caption,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            elif update.effective_chat:
                context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=caption,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
    except Exception as e:
        logger.error(f"[PROFILE ERROR] {e}", exc_info=True)
        try:
            if update.effective_message:
                update.effective_message.reply_text("⚠️ Could not load profile. Please try again.")
        except Exception:
            pass

