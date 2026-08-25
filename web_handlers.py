import html
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import CallbackContext
from config import WEB_APP_URL


def web_cmd(update: Update, context: CallbackContext):
    """Sends the Manga Galactic Web Mini App launch button."""
    user = update.effective_user
    name = html.escape(user.first_name if user else "Reader")
    bot_username = context.bot.username or "Galactic_Update_bot"
    is_private = update.effective_chat.type == "private" if update.effective_chat else True

    text = (
        f"🌌 <b>Manga Galactic Web Mini App</b> 🛸\n\n"
        f"Hey <b>{name}</b>! Explore our entire manga and manhwa catalog in an interactive, high-speed web interface.\n\n"
        f"✨ <b>Web App Features:</b>\n"
        f"• 🔍 Instant live search & title filtering\n"
        f"• 📚 Manga covers, chapter counts & read links\n"
        f"• 🔖 One-tap Bookmarks, Favorites, Completed & Reading lists\n"
        f"• ⚡ Real-time synchronization with Telegram bot database\n\n"
        f"<i>Tap the button below to launch the Web App!</i> 👇"
    )

    if is_private:
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Launch Manga Galactic", web_app=WebAppInfo(url=f"{WEB_APP_URL}/web"))],
            [
                InlineKeyboardButton("🛸 Open Web Hub", web_app=WebAppInfo(url=f"{WEB_APP_URL}/webhub")),
                InlineKeyboardButton("🔍 Search Inline", switch_inline_query_current_chat="")
            ]
        ])
    else:
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Launch Manga Galactic", url=f"https://t.me/{bot_username}?start=web")],
            [
                InlineKeyboardButton("🛸 Open Web Hub", url=f"https://t.me/{bot_username}?start=webhub"),
                InlineKeyboardButton("🔍 Search Inline", switch_inline_query_current_chat="")
            ]
        ])

    msg = update.effective_message or update.message
    if msg:
        msg.reply_text(text, parse_mode="HTML", reply_markup=buttons)
    elif update.effective_chat:
        context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode="HTML", reply_markup=buttons)


def webprofile_cmd(update: Update, context: CallbackContext):
    """Sends the Web Profile launch button."""
    webhub_cmd(update, context)


def webhub_cmd(update: Update, context: CallbackContext):
    """Sends the Manga Galactic Web Hub & Shelves Mini App launch card."""
    user = update.effective_user
    name = html.escape(user.first_name if user else "Reader")
    user_id = user.id if user else 0
    bot_username = context.bot.username or "Galactic_Update_bot"
    is_private = update.effective_chat.type == "private" if update.effective_chat else True

    text = (
        f"🛸 <b>Galactic Web Hub & Reading Dashboard</b> 🌌\n\n"
        f"Hey <b>{name}</b>! Access your complete personal manga command center in the Web Mini App:\n\n"
        f"✨ <b>Web Hub Features:</b>\n"
        f"• 📊 Real-time synced shelves (Read, Favorites, Completed, Hold, Dropped)\n"
        f"• 📌 Direct chapter bookmarks & instant webtoon resume\n"
        f"• 🏅 Reader ranks, cosmic badges & XP level tracker\n"
        f"• 🔍 Instant inline & live search across 125+ manga\n"
        f"• ⚡ One-tap synchronization with Telegram bot database\n\n"
        f"<i>Tap below to launch your Web Hub or search manga inline!</i> 👇"
    )

    if is_private:
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛸 Launch Web Hub", web_app=WebAppInfo(url=f"{WEB_APP_URL}/webhub"))],
            [
                InlineKeyboardButton("📚 Manga Catalog", web_app=WebAppInfo(url=f"{WEB_APP_URL}/web")),
                InlineKeyboardButton("🔍 Search Inline", switch_inline_query_current_chat="")
            ],
            [
                InlineKeyboardButton("🛸 Bot Hub", callback_data=f"hub_back:{user_id}")
            ]
        ])
    else:
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛸 Launch Web Hub", url=f"https://t.me/{bot_username}?start=webhub")],
            [
                InlineKeyboardButton("📚 Manga Catalog", url=f"https://t.me/{bot_username}?start=web"),
                InlineKeyboardButton("🔍 Search Inline", switch_inline_query_current_chat="")
            ],
            [
                InlineKeyboardButton("🛸 Bot Hub", url=f"https://t.me/{bot_username}?start=hub")
            ]
        ])

    msg = update.effective_message or update.message
    if msg:
        msg.reply_text(text, parse_mode="HTML", reply_markup=buttons)
    elif update.effective_chat:
        context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode="HTML", reply_markup=buttons)

