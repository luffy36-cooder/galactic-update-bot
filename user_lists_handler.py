from telegram import Update
from telegram.ext import CallbackContext
from database import get_user_manga_lists, get_manga_by_id

# ✨ Helper to format a list of manga names from channel IDs
def format_manga_list(channel_ids):
    if not channel_ids:
        return "None 🥺"

    lines = []
    for cid in channel_ids:
        info = get_manga_by_id(cid)
        if info:
            name = info.get("name", "Unknown")
            link = info.get("channel_link", f"https://t.me/c/{str(cid)[4:]}/1")
            lines.append(f"• <a href='{link}'>{name}</a>")
        else:
            lines.append(f"• Unknown (ID: {cid})")
    return "\n".join(lines)

# ✅ /readlist and /read
def readlist_cmd(update: Update, context: CallbackContext):
    read_cmd(update, context)

def read_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    lists = get_user_manga_lists(user_id)
    text = f"📖 <b>Your Read List:</b>\n{format_manga_list(lists['read'])}"
    update.message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)

# ✅ /favorites and /fav
def favorites_cmd(update: Update, context: CallbackContext):
    fav_cmd(update, context)

def fav_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    lists = get_user_manga_lists(user_id)
    text = f"❤️ <b>Your Favorites:</b>\n{format_manga_list(lists['favorite'])}"
    update.message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)

# ✅ /completed
def completed_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    lists = get_user_manga_lists(user_id)
    text = f"🏁 <b>Your Completed List:</b>\n{format_manga_list(lists['completed'])}"
    update.message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)

# ✅ /hold
def hold_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    lists = get_user_manga_lists(user_id)
    text = f"⏸️ <b>Your On Hold Manga:</b>\n{format_manga_list(lists['hold'])}"
    update.message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)

# ✅ /drop
def drop_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    lists = get_user_manga_lists(user_id)
    text = f"👋 <b>Your Dropped Manga:</b>\n{format_manga_list(lists['dropped'])}"
    update.message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)

# ✅ /currentlyreading
def currentlyreading_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    lists = get_user_manga_lists(user_id)

    all_ids = set(lists['read']) | set(lists['favorite'])
    excluded_ids = set(lists['completed']) | set(lists['dropped'])
    reading_now = list(all_ids - excluded_ids)

    text = f"📘 <b>Currently Reading:</b>\n{format_manga_list(reading_now)}"
    update.message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)

# ✅ /mylist – summary of all
def mylist_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    lists = get_user_manga_lists(user_id)

    text = (
        "📚 <b>Your Manga List Summary</b>\n\n"
        f"📖 <b>Read:</b>\n{format_manga_list(lists['read'])}\n\n"
        f"❤️ <b>Favorites:</b>\n{format_manga_list(lists['favorite'])}\n\n"
        f"🏁 <b>Completed:</b>\n{format_manga_list(lists['completed'])}\n\n"
        f"👋 <b>Dropped:</b>\n{format_manga_list(lists['dropped'])}\n\n"
        f"⏸️ <b>On Hold:</b>\n{format_manga_list(lists['hold'])}"
    )
    update.message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)


# =========================================================
# 🛸 /myhub & /hub — Personal Interactive Manga Hub Dashboard
# =========================================================
def hub_cmd(update: Update, context: CallbackContext):
    myhub_cmd(update, context)


def myhub_cmd(update: Update, context: CallbackContext):
    import html
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    from config import WEB_APP_URL
    from database import get_user_bookmarks, get_user_badges

    user = update.effective_user
    user_id = user.id
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
        f"👤 <b>Reader:</b> {html.escape(user.full_name)}\n"
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

    update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)

