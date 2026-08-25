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
# ✅ Group & PM text-based search mode
# ===============================
def search_by_text_if_enabled(update: Update, context: CallbackContext):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    if not text or text.startswith("/"):
        return

    # Route request commands directly to request_handler
    text_lower = text.lower()
    if text_lower.startswith("#request") or text_lower.startswith("request"):
        from request_handler import request_manga
        return request_manga(update, context)

    chat = update.effective_chat
    if not chat:
        return

    # In groups, check if text mode is enabled
    if chat.type in ["group", "supergroup"]:
        mode = get_group_mode(chat.id)
        if mode != "text":
            return
        if len(text.split()) > 8:
            return
    elif chat.type == "private":
        # In private chat, allow direct text search
        if len(text.split()) > 10:
            return

    send_search_result(update, context, text)


# ========================
# 🔍 Search result handler
# ========================
def send_search_result(update_or_query, context: CallbackContext, query: str):
    results = search_manga_by_name(query, limit=6)

    if not results:
        send_message(
            update_or_query,
            "⚠️ <b>No matching manga found.</b>\nTry checking the spelling, using a shorter title, or request it with <code>/request &lt;name&gt;</code>.",
            parse_mode="HTML"
        )
        return

    # Multiple results → ask user to pick with rich buttons
    if len(results) > 1:
        user_id = get_user_id(update_or_query)
        buttons = []
        for m in results:
            m_name = m.get("name", "Unknown").title()
            ch_count = m.get("total_chapters")
            ch_str = f" ({ch_count} ch)" if ch_count else ""
            label = f"📚 {m_name[:32]}{ch_str}"
            buttons.append([InlineKeyboardButton(label, callback_data=f"select_{m['channel_id']}_{user_id}")])

        keyboard = InlineKeyboardMarkup(buttons)
        send_message(
            update_or_query,
            f"🔎 Found <b>{len(results)} matches</b> for <code>{html.escape(query)}</code>. Please select:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
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

    # Action buttons
    channel_link = result.get("channel_link") or (f"https://t.me/c/{str(cid)[4:]}/1" if cid else "https://t.me")
    buttons = [
        [
            InlineKeyboardButton("📖 Read in Channel", url=channel_link),
            InlineKeyboardButton(f"{'🔕 Subscribed' if is_sub else '🔔 Subscribe'}", callback_data=f"subtoggle_{cid}_{user_id}")
        ],
        [
            InlineKeyboardButton("⭐ Rate (1-5★)", callback_data=f"showrate_{cid}_{user_id}")
        ]
    ]

    status_buttons = [
        ("favorite", "❤️ Favorite", "💔 Unfavorite"),
        ("read", "✅ Mark Read", "❌ Unread"),
        ("completed", "🏁 Completed", "🚫 Uncompleted"),
        ("hold", "⏸️ On Hold", "🔄 Unhold"),
        ("dropped", "👋 Drop", "♻️ Undrop")
    ]

    # Add favorite to row 2 next to Rate
    is_fav_active = "favorite" in status
    fav_display = "💔 Unfavorite" if is_fav_active else "❤️ Favorite"
    fav_action = "unfav" if is_fav_active else "fav"
    buttons[1].append(InlineKeyboardButton(fav_display, callback_data=f"{fav_action}_{cid}_{user_id}"))

    # Remaining status buttons in 2-column rows
    remaining_status = [
        ("read", "✅ Mark Read", "❌ Unread"),
        ("completed", "🏁 Completed", "🚫 Uncompleted"),
        ("hold", "⏸️ On Hold", "🔄 Unhold"),
        ("dropped", "👋 Drop", "♻️ Undrop")
    ]

    row = []
    for stat, add_text, remove_text in remaining_status:
        is_active = stat in status
        action_map = {
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

    # Add Web Reader & My Hub navigation row
    buttons.append([
        InlineKeyboardButton("🌐 Web Reader", web_app=WebAppInfo(url=f"{WEB_APP_URL}/reader?channel_id={cid}&ch=1")),
        InlineKeyboardButton("🛸 My Hub", callback_data=f"hub_back:{user_id}")
    ])

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
        # In-place message edit for callback queries
        if hasattr(update_or_query, "callback_query") and update_or_query.callback_query:
            query = update_or_query.callback_query
            try:
                if query.message and query.message.photo:
                    try:
                        query.edit_message_caption(caption=caption, parse_mode="HTML", reply_markup=keyboard)
                        return
                    except Exception:
                        query.edit_message_reply_markup(reply_markup=keyboard)
                        return
                elif query.message:
                    query.edit_message_text(text=caption, parse_mode="HTML", reply_markup=keyboard)
                    return
            except Exception:
                pass

        # Sending new message (from command or search)
        msg = getattr(update_or_query, "message", None) or getattr(update_or_query, "effective_message", None)
        chat = getattr(update_or_query, "effective_chat", None)

        if result.get("image"):
            try:
                if msg:
                    msg.reply_photo(photo=result["image"], caption=caption, parse_mode="HTML", reply_markup=keyboard)
                    return
                elif chat:
                    chat.send_photo(photo=result["image"], caption=caption, parse_mode="HTML", reply_markup=keyboard)
                    return
            except Exception:
                pass

        if msg:
            msg.reply_text(caption, parse_mode="HTML", reply_markup=keyboard)
        elif chat:
            chat.send_message(text=caption, parse_mode="HTML", reply_markup=keyboard)
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
