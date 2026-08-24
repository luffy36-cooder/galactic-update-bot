import html
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import CallbackContext
from config import WEB_APP_URL


def web_cmd(update: Update, context: CallbackContext):
    """Sends the Manga Galactic Web Mini App launch button."""
    user = update.effective_user
    name = html.escape(user.first_name or "Reader")
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
            [InlineKeyboardButton("👤 Open Web Profile", web_app=WebAppInfo(url=f"{WEB_APP_URL}/webprofile"))]
        ])
    else:
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Launch Manga Galactic", url=f"https://t.me/{bot_username}?start=web")],
            [InlineKeyboardButton("👤 Open Web Profile", url=f"https://t.me/{bot_username}?start=webprofile")]
        ])

    if update.message:
        update.message.reply_text(text, parse_mode="HTML", reply_markup=buttons)
    elif update.effective_chat:
        update.effective_chat.send_message(text, parse_mode="HTML", reply_markup=buttons)


def webprofile_cmd(update: Update, context: CallbackContext):
    """Sends the Web Profile launch button."""
    user = update.effective_user
    name = html.escape(user.first_name or "Reader")
    bot_username = context.bot.username or "Galactic_Update_bot"
    is_private = update.effective_chat.type == "private" if update.effective_chat else True

    text = (
        f"👤 <b>Your Galactic Reader Profile (Web Edition)</b> 🌟\n\n"
        f"View your advanced reader dashboard with interactive shelves, achievements, badges, and reading metrics.\n\n"
        f"<i>Tap below to open your profile in the Web Mini App!</i> 👇"
    )

    if is_private:
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("👤 Open Web Profile", web_app=WebAppInfo(url=f"{WEB_APP_URL}/webprofile"))],
            [InlineKeyboardButton("📚 Browse Manga Catalog", web_app=WebAppInfo(url=f"{WEB_APP_URL}/web"))]
        ])
    else:
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("👤 Open Web Profile", url=f"https://t.me/{bot_username}?start=webprofile")],
            [InlineKeyboardButton("📚 Browse Manga Catalog", url=f"https://t.me/{bot_username}?start=web")]
        ])

    if update.message:
        update.message.reply_text(text, parse_mode="HTML", reply_markup=buttons)
    elif update.effective_chat:
        update.effective_chat.send_message(text, parse_mode="HTML", reply_markup=buttons)
