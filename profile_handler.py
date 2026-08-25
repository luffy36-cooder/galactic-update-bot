import html
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext
from database import (
    get_user_profile,
    get_user_badges,
    get_user_manga_lists
)

# ⭐ Rank system
def get_rank_title(read_count: int) -> str:
    if read_count >= 50:
        return "📚 Elite Reader"
    elif read_count >= 25:
        return "🌟🌟🌟🌟 Reader"
    elif read_count >= 15:
        return "🌟🌟🌟 Reader"
    elif read_count >= 10:
        return "🌟🌟 Reader"
    elif read_count >= 1:
        return "🌟 Reader"
    return "📥 Newbie"


# 🖼️ /profile command (with user-bound inline button)
def profile_cmd(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = user.id

    # DB Fetch
    profile = get_user_profile(user_id)
    badges = get_user_badges(user_id)
    manga_lists = get_user_manga_lists(user_id)

    # Count values
    bookmark_count = profile.get("bookmarks", 0)
    read_count = len(manga_lists.get("read", []))
    completed_count = len(manga_lists.get("completed", []))
    fav_count = len(manga_lists.get("favorite", []))
    drop_count = len(manga_lists.get("dropped", []))
    hold_count = len(manga_lists.get("hold", []))
    rank = get_rank_title(read_count)

    badge_display = " ".join(badges) if badges else "No badges yet 🥺"
    safe_name = html.escape(user.full_name or "Unknown")
    safe_username = f"@{html.escape(user.username)}" if user.username else "N/A"

    # Caption
    caption = (
        f"👤 <b>Reader Profile</b>\n"
        f"• <b>Name:</b> {safe_name}\n"
        f"• <b>Username:</b> {safe_username}\n"
        f"• <b>User ID:</b> <code>{user_id}</code>\n\n"
        f"📚 <b>Bookmarks:</b> {bookmark_count}\n"
        f"📖 <b>Read:</b> {read_count}  🏁 <b>Completed:</b> {completed_count}  ❤️ <b>Favorites:</b> {fav_count}\n"
        f"👋 <b>Dropped:</b> {drop_count}  ⏸️ <b>Hold:</b> {hold_count}\n"
        f"🏅 <b>Rank:</b> {rank}\n\n"
        f"🎖️ <b>Badges:</b>\n{badge_display}"
    )

    # Inline buttons (secured with user_id)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🛸 My Hub", callback_data=f"hub_back:{user_id}"),
            InlineKeyboardButton("📜 View My Lists", callback_data=f"view_mylist:{user_id}")
        ]
    ])

    # Try sending profile pic
    photo_sent = False
    try:
        context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_photo")
        photos = context.bot.get_user_profile_photos(user_id, limit=1)
        if photos and photos.total_count > 0:
            update.message.reply_photo(
                photo=photos.photos[0][0].file_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard
            )
            photo_sent = True
    except Exception as e:
        pass

    # Fallback to text message if photo could not be sent or user has no photo
    if not photo_sent:
        update.message.reply_text(
            caption,
            parse_mode="HTML",
            reply_markup=keyboard
        )
