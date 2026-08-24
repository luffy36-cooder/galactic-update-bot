from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext
from database import (
    search_manga_by_name,
    get_user_manga_status,
    get_group_mode
)
from rapidfuzz import fuzz, process

# ========================
# ✅ /manga command handler
# ========================
def search_by_command(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("🔍 Usage: /manga <name>")
        return
    query = " ".join(context.args).strip()
    send_search_result(update, context, query)

# ===============================
# ✅ Group text-based search mode
# ===============================
def search_by_text_if_enabled(update: Update, context: CallbackContext):
    chat = update.effective_chat
    if chat.type not in ["group", "supergroup"]:
        return

    mode = get_group_mode(chat.id)
    if mode != "text":
        return

    text = update.message.text.strip()
    if not text or len(text.split()) > 6:
        return

    send_search_result(update, context, text)

# ========================
# 🔍 Search result handler
# ========================
def send_search_result(update_or_query, context: CallbackContext, query: str):
    results = search_manga_by_name(query)

    if not results:
        send_message(update_or_query, "⚠️ No matching manga found.\nTry checking the spelling or use a shorter title.")
        return

    # Multiple results → ask user to pick
    if len(results) > 1:
        user_id = get_user_id(update_or_query)
        buttons = [
            [InlineKeyboardButton(m["name"].title(), callback_data=f"select_{m['channel_id']}_{user_id}")]
            for m in results
        ]
        keyboard = InlineKeyboardMarkup(buttons)
        send_message(update_or_query,
                     f"🔎 Found multiple matches for <b>{query}</b>. Please select:",
                     reply_markup=keyboard,
                     parse_mode="HTML")
        return

    # Only one result → show manga info
    _send_single_manga(update_or_query, results[0])

# =====================================
# 🔘 Display single manga with buttons
# =====================================
def _send_single_manga(update_or_query, result: dict):
    user_id = get_user_id(update_or_query)
    status = get_user_manga_status(user_id, result["channel_id"]) or []

    buttons = [[InlineKeyboardButton("📖 Read",
                                     url=result.get("channel_link") or f"https://t.me/c/{str(result['channel_id'])[4:]}/1")]]

    status_buttons = [
        ("read", "✅ Mark as Read", "❌ Remove Read"),
        ("completed", "🏁 Mark as Completed", "🚫 Remove Completed"),
        ("favorite", "❤️ Add to Favorites", "💔 Remove Favorite"),
        ("dropped", "👋 Drop", "♻️ Undrop"),
        ("hold", "⏸️ Hold", "🔄 Unhold")
    ]

    for stat, add_text, remove_text in status_buttons:
        is_active = stat in status
        action_map = {
            "favorite": "fav" if not is_active else "unfav",
            "completed": "complete" if not is_active else "uncomplete",
            "dropped": "drop" if not is_active else "undrop",
            "hold": "hold" if not is_active else "unhold",
            "read": "read" if not is_active else "unread",
        }
        action = action_map.get(stat, stat)
        display = remove_text if is_active else add_text
        callback = f"{action}_{result['channel_id']}_{user_id}"
        buttons.append([InlineKeyboardButton(display, callback_data=callback)])

    keyboard = InlineKeyboardMarkup(buttons)
    caption = f"<b>{result['name'].title()}</b>\nClick below to read or mark status 👇"

    try:
        if hasattr(update_or_query, "callback_query") and update_or_query.callback_query:
            query = update_or_query.callback_query
            if result.get("image"):
                query.message.reply_photo(photo=result["image"], caption=caption,
                                          parse_mode="HTML", reply_markup=keyboard)
            else:
                query.message.reply_text(caption, parse_mode="HTML", reply_markup=keyboard)
        else:
            if result.get("image"):
                update_or_query.message.reply_photo(photo=result["image"], caption=caption,
                                                    parse_mode="HTML", reply_markup=keyboard)
            else:
                update_or_query.message.reply_text(caption, parse_mode="HTML", reply_markup=keyboard)
    except Exception as e:
        print(f"[⚠️ Error sending manga result] {e}")
        send_message(update_or_query, f"<b>{result['name'].title()}</b>\n📖 {result.get('channel_link')}")

# =========================
# 🔹 Helper: Send message
# =========================
def send_message(update_or_query, text, reply_markup=None, parse_mode=None):
    if hasattr(update_or_query, "callback_query") and update_or_query.callback_query:
        update_or_query.callback_query.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    else:
        update_or_query.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)

# =====================================
# 🔹 Helper: Get user id from Update or CallbackQuery
# =====================================
def get_user_id(update_or_query):
    if hasattr(update_or_query, "callback_query") and update_or_query.callback_query:
        return update_or_query.callback_query.from_user.id
    else:
        return update_or_query.effective_user.id
