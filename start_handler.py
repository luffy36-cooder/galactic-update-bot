import random
import json
from datetime import datetime
from pytz import timezone
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import CallbackContext
from config import LOG_CHANNEL_ID, WEB_APP_URL

# Load quotes and facts
with open("anime_quotes.json", encoding="utf-8") as f:
    anime_quotes = json.load(f)

with open("manga_facts.json", encoding="utf-8") as f:
    manga_facts = json.load(f)

greeting_emojis = ["🌠", "✨", "🌌", "🚀", "📖", "💫", "🌟"]

# Reusable logging function
def log_to_channel(context: CallbackContext, text: str):
    try:
        context.bot.send_message(
            chat_id=LOG_CHANNEL_ID,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"[Log Error] {e}")

# /start command
def start_cmd(update: Update, context: CallbackContext):
    user = update.effective_user.first_name or "Senpai"
    user_id = update.effective_user.id
    india_time = datetime.now(timezone("Asia/Kolkata"))
    hour = india_time.hour

    if hour < 6:
        greeting = "🌙 The night is yours to conquer..."
    elif hour < 12:
        greeting = "☀ New manga morning calls!"
    elif hour < 18:
        greeting = "🌤 Afternoon adventures await!"
    else:
        greeting = "🌌 Evening stars guide your pages."

    text = (
        f"<b>{random.choice(greeting_emojis)} Welcome to <u>Manga Galactic</u>!</b>\n"
        f"<i>{greeting}</i>\n\n"
        f"Hey <b>{user}</b> 🌠\n\n"
        f"💬 <i>{random.choice(anime_quotes)}</i>\n"
        f"{random.choice(manga_facts)}\n\n"
        "🔓 Or just tap one of these commands:\n"
        "/read | /bookmark | /request | /help"
    )

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Launch Manga Web App", web_app=WebAppInfo(url=f"{WEB_APP_URL}/web"))],
        [InlineKeyboardButton("👤 Web Profile", web_app=WebAppInfo(url=f"{WEB_APP_URL}/webprofile")),
         InlineKeyboardButton("🧰 Commands", callback_data="help_search")],
        [InlineKeyboardButton("📚 My List", callback_data="help_lists"),
         InlineKeyboardButton("📌 Bookmarks", callback_data="help_bookmarks")],
        [InlineKeyboardButton("🔍 Search", switch_inline_query_current_chat=""),
         InlineKeyboardButton("🌟 Recommend", callback_data="help_recommend"),
         InlineKeyboardButton("🥇 Leaderboard", callback_data="help_leaderboard")],
        [InlineKeyboardButton("📊 Stats", callback_data="help_stats"),
         InlineKeyboardButton("🎛 Dashboard", callback_data="help_admin")]
    ])

    if update.message:
        update.message.reply_animation(
            animation="https://media.tenor.com/RHX4riDnxscAAAPo/its-time-to-read-manga.mp4",
            caption=text,
            parse_mode="HTML",
            reply_markup=buttons
        )
    else:
        update.effective_chat.send_animation(
            animation="https://media.tenor.com/RHX4riDnxscAAAPo/its-time-to-read-manga.mp4",
            caption=text,
            parse_mode="HTML",
            reply_markup=buttons
        )

    # 📝 Log start command
    log_to_channel(context, f"🚀 <b>/start used</b> by <code>{user}</code> (ID: <code>{user_id}</code>)")

# /help command
def help_cmd(update: Update, context: CallbackContext):
    user = update.effective_user.first_name
    user_id = update.effective_user.id

    text = (
        "📖 <b>Full Command Guide</b>\n\n"
        "Here's your command spellbook, senpai~ 🪄\n\n"

        "🔍 Search:\n"
        "/manga One Piece — Search for a manga\n"
        "Inline: <code>@YourBotUsername Naruto</code>\n\n"

        "📌 Bookmarks:\n"
        "/bookmark Nano Machine 200 — Add & track progress\n"
        "/mybookmarks — View & manage\n\n"

        "📚 Reading List:\n"
        "/read | /fav | /drop | /hold\n"
        "/currentlyreading — Ongoing titles\n"
        "/mylist — Summary of all\n\n"

        "📨 Requests:\n"
        "/request Solo Leveling — Ask for missing manga\n"
        "/requestlist — View all requests (Sudo only)\n\n"

        "🌟 Recommendations:\n"
        "/recommend — Based on your favorites\n\n"

        "🥇 Leaderboard:\n"
        "/leaderboard — Top readers by chapters\n\n"

        "🛠 Admin Tools:\n"
        "/add &lt;channel_id&gt; &lt;manga name&gt;\n"
        "/unpost &lt;channel_id&gt; &lt;chapter&gt;\n"
        "/removemanga &lt;name&gt;\n"
        "/editmanga &lt;old&gt; &lt;new&gt;\n"
        "/listmanga\n"
        "/setchapters &lt;manga&gt; &lt;total&gt;\n\n"

        "🎛 Group Mode:\n"
        "/setmode text — Auto-search mode\n"
        "/setmode command — Use /manga only\n\n"

        "📊 Stats:\n"
        "/stats — Total manga, users, groups"
    )
    update.message.reply_text(text, parse_mode="HTML")

    # 📝 Log help command
    log_to_channel(context, f"📖 <b>/help used</b> by <code>{user}</code> (ID: <code>{user_id}</code>)")

# Inline help button handler
def help_button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    section_texts = {
        "help_search": (
            "🔍 <b>Search Commands</b>\n\n"
            "/manga One Piece — Search by name\n"
            "Inline: <code>@YourBotUsername Naruto</code>\n"
            "Groups (text mode): Just type the name!"
        ),
        "help_bookmarks": (
            "📌 <b>Bookmark System</b>\n\n"
            "/bookmark Solo Leveling 179 — Save & track\n"
            "/mybookmarks — View, edit, remove"
        ),
        "help_lists": (
            "📚 <b>Your Reading List</b>\n\n"
            "/read | /fav | /drop | /hold\n"
            "/currentlyreading — Ongoing manga\n"
            "/mylist — Full summary"
        ),
        "help_requests": (
            "📨 <b>Manga Requests</b>\n\n"
            "/request Return of the Mount Hua Sect — Suggest manga\n"
            "/requestlist — View requests (Sudo only)"
        ),
        "help_recommend": (
            "🌟 <b>Get Recommendations</b>\n\n"
            "/recommend — Based on your favs and reading"
        ),
        "help_leaderboard": (
            "🥇 <b>Leaderboard</b>\n\n"
            "/leaderboard — Top manga readers 📈"
        ),
        "help_admin": (
            "🛠 <b>Admin Tools</b>\n\n"
            "/add &lt;channel_id&gt; &lt;manga name&gt;\n"
            "/unpost &lt;channel_id&gt; &lt;chapter&gt;\n"
            "/removemanga &lt;name&gt;\n"
            "/editmanga &lt;old&gt; &lt;new&gt;\n"
            "/listmanga\n"
            "/setchapters &lt;manga&gt; &lt;total&gt;"
        ),
        "help_stats": (
            "📊 <b>Bot Stats</b>\n\n"
            "/stats — Manga, users, groups"
        ),
    }

    text = section_texts.get(query.data, "❓ Unknown help section.")
    query.edit_message_caption(caption=text, parse_mode="HTML")

    # 📝 Log button tap
    log_to_channel(context, f"🔘 <b>Help Section Opened:</b> <code>{query.data}</code>\n👤 <code>{query.from_user.full_name}</code> (ID: <code>{query.from_user.id}</code>)")
