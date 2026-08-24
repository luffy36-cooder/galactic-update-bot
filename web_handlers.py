import html
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import CallbackContext
from config import WEB_APP_URL


def web_cmd(update: Update, context: CallbackContext):
    """Sends the Manga Galactic Web Mini App launch button."""
    user = update.effective_user
    name = html.escape(user.first_name or "Reader")

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

    web_url = f"{WEB_APP_URL}/web"
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Launch Manga Galactic", web_app=WebAppInfo(url=web_url))],
        [InlineKeyboardButton("👤 Open Web Profile", web_app=WebAppInfo(url=f"{WEB_APP_URL}/webprofile"))]
    ])

    update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=buttons
    )


def webprofile_cmd(update: Update, context: CallbackContext):
    """Sends the Web Profile launch button."""
    user = update.effective_user
    name = html.escape(user.first_name or "Reader")

    text = (
        f"👤 <b>Your Galactic Reader Profile (Web Edition)</b> 🌟\n\n"
        f"View your advanced reader dashboard with interactive shelves, achievements, badges, and reading metrics.\n\n"
        f"<i>Tap below to open your profile in the Web Mini App!</i> 👇"
    )

    profile_url = f"{WEB_APP_URL}/webprofile"
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Open Web Profile", web_app=WebAppInfo(url=profile_url))],
        [InlineKeyboardButton("📚 Browse Manga Catalog", web_app=WebAppInfo(url=f"{WEB_APP_URL}/web"))]
    ])

    update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=buttons
    )
