import html
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import CallbackContext
from database import (
    search_manga_by_name,
    get_user_manga_status,
    get_group_mode,
    get_manga_rating_summary,
    is_user_subscribed
)
from config import WEB_APP_URL


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

    text = (update.message.text or "").strip()
    if not text:
        return

    # Route #request <name> or request <name> directly to request_manga
    if text.lower().startswith("#request") or text.lower().startswith("request "):
        from request_handler import request_manga
        return request_manga(update, context)

    mode = get_group_mode(chat.id)
    if mode != "text":
        return

    if len(text.split()) > 6:
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
                     f"🔎 Found multiple matches for <b>{html.escape(query)}</b>. Please select:",
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
    cid = result.get("channel_id")
    status = get_user_manga_status(user_id, cid) if cid else []
    rating_data = get_manga_rating_summary(cid, user_id) if cid else {}
    is_sub = is_user_subscribed(user_id, cid) if cid else False

    # Rating badge
    avg = rating_data.get("avg_rating", 0.0)
    count = rating_data.get("total_ratings", 0)
    user_rat = rating_data.get("user_rating")
    
    if count > 0:
        stars_str = f"⭐ <b>{avg}/5.0</b> ({count} {'review' if count == 1 else 'reviews'})"
    else:
        stars_str = "⭐ <i>No ratings yet</i>"

    if user_rat:
        stars_str += f" • <i>Your rating: {user_rat}★</i>"

    # Determine if chat is private
    chat = getattr(update_or_query, 'effective_chat', None) or getattr(getattr(update_or_query, 'message', None), 'chat', None)
    is_private = (chat.type == 'private') if chat else True

    # Action buttons
    channel_link = result.get("channel_link") or (f"https://t.me/c/{str(cid)[4:]}/1" if cid else "https://t.me")
    reader_url = f"{WEB_APP_URL}/reader?cid={cid}&ch=1&user_id={user_id}"
    profile_url = f"{WEB_APP_URL}/webprofile"

    if is_private:
        read_btn = InlineKeyboardButton("🚀 Read Online (App)", web_app=WebAppInfo(url=reader_url))
        profile_btn = InlineKeyboardButton("👤 Web Profile", web_app=WebAppInfo(url=profile_url))
    else:
        read_btn = InlineKeyboardButton("🚀 Read Online (App)", url=reader_url)
        profile_btn = InlineKeyboardButton("👤 Web Profile", url=profile_url)

    buttons = [
        [
            InlineKeyboardButton("📖 Read in Channel", url=channel_link),
            read_btn
        ],
        [
            InlineKeyboardButton(f"{'🔕 Subscribed' if is_sub else '🔔 Subscribe'}", callback_data=f"subtoggle_{cid}_{user_id}"),
            InlineKeyboardButton("⭐ Rate (1-5★)", callback_data=f"showrate_{cid}_{user_id}")
        ]
    ]

    status_buttons = [
        ("read", "✅ Mark Read", "❌ Unread"),
        ("favorite", "❤️ Favorite", "💔 Unfavorite"),
        ("completed", "🏁 Completed", "🚫 Uncompleted"),
        ("hold", "⏸️ On Hold", "🔄 Unhold"),
        ("dropped", "👋 Drop", "♻️ Undrop")
    ]

    # Grid of status buttons (2 per row)
    row = []
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
        callback = f"{action}_{cid}_{user_id}"
        row.append(InlineKeyboardButton(display, callback_data=callback))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        row.append(profile_btn)
        buttons.append(row)

    keyboard = InlineKeyboardMarkup(buttons)
    safe_name = html.escape(result.get("name", "Manga").title())
    total_chap = result.get("total_chapters")
    chap_info = f" • <b>{total_chap}</b> chapters" if total_chap else ""

    caption = (
        f"📚 <b>{safe_name}</b>{chap_info}\n"
        f"{stars_str}\n\n"
        f"<i>Tap below to read, subscribe to new chapter alerts, or track your reading status:</i>"
    )

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
        send_message(update_or_query, f"<b>{safe_name}</b>\n📖 {channel_link}", parse_mode="HTML")


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
