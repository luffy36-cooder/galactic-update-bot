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
