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
    user = update.effective_user.first_name or "Senpai"
    user_id = update.effective_user.id
    bot_username = context.bot.username or "Galactic_Update_bot"

    text = (
        "🌌 <b>Galactic Manga Bot — Command Guide</b> 📖\n\n"
        f"Hey <b>{user}</b>! Here are all the powerful features you can use:\n\n"

        "🌐 <b>Web Mini App & In-App Reader:</b>\n"
        "• <code>/web</code> — Launch Full Manga Catalog & Live Reader 🚀\n"
        "• <code>/webprofile</code> — Open your Visual Gamified Cosmic Profile 👤\n\n"

        "🔍 <b>Manga Search & Reading:</b>\n"
        "• <code>/manga &lt;name&gt;</code> — Search manga with ratings & status buttons\n"
        f"• Inline: <code>@{bot_username} Naruto</code> — Share manga in any chat\n\n"

        "📨 <b>Manga Requests System:</b>\n"
        "• <code>/request &lt;name&gt;</code> (or <code>#request &lt;name&gt;</code> / <code>request &lt;name&gt;</code>)\n"
        "<i>Instant already-uploaded check, duplicate prevention, and direct admin DM response!</i>\n\n"

        "📌 <b>Smart Bookmarks:</b>\n"
        "• <code>/bookmark &lt;name&gt; &lt;ch&gt;</code> — Save your reading chapter progress\n"
        "• <code>/mybookmarks</code> — View & jump back to your saved chapters\n"
        "• <code>/clearbookmarks</code> — Clear saved bookmarks\n\n"

        "📚 <b>Reading Shelves & Tracking:</b>\n"
        "• <code>/read</code> | <code>/fav</code> | <code>/completed</code> | <code>/hold</code> | <code>/drop</code>\n"
        "• <code>/currentlyreading</code> — View active ongoing manga\n"
        "• <code>/mylist</code> — Complete reading summary\n\n"

        "⭐ <b>Ratings & Community Leaderboard:</b>\n"
        "• <code>/toprated</code> — Top community-rated manga leaderboard ⭐\n"
        "• <code>/leaderboard</code> — Top reader rankings & chapters read 🏆\n"
        "• <code>/recommend</code> — Personalized recommendations\n\n"

        "🔔 <b>New Chapter DM Alerts:</b>\n"
        "• Tap 🔔 Subscribe on any manga to get instant alerts whenever new chapters drop!\n\n"

        "🛡️ <b>Admin & Sudo Commands:</b>\n"
        "• <code>/scanallchannels</code> — High-speed past PDF channel scanner 🛰️\n"
        "• <code>/syncchapters</code> — Auto-sync chapter numbers\n"
        "• <code>/add &lt;channel_id&gt; &lt;name&gt;</code> — Register a manga channel\n"
        "• <code>/requestlist</code> — Review pending requests\n"
        "• <code>/replyreq &lt;user_id&gt; &lt;msg&gt;</code> — Direct admin DM to user\n"
        "• <code>/broadcast</code> & <code>/dmbroadcast</code> — Announce updates"
    )

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Open Manga Web App", web_app=WebAppInfo(url=f"{WEB_APP_URL}/web")),
         InlineKeyboardButton("👤 Web Profile", web_app=WebAppInfo(url=f"{WEB_APP_URL}/webprofile"))],
        [InlineKeyboardButton("🔍 Search Help", callback_data="help_search"),
         InlineKeyboardButton("📌 Bookmarks Help", callback_data="help_bookmarks")],
        [InlineKeyboardButton("📨 Requests Help", callback_data="help_requests"),
         InlineKeyboardButton("📚 Shelves Help", callback_data="help_lists")],
        [InlineKeyboardButton("🥇 Leaderboard Help", callback_data="help_leaderboard"),
         InlineKeyboardButton("🛠 Admin Help", callback_data="help_admin")]
    ])

    update.message.reply_text(text, parse_mode="HTML", reply_markup=buttons)
    log_to_channel(context, f"📖 <b>/help used</b> by <code>{user}</code> (ID: <code>{user_id}</code>)")


# Inline help button handler
def help_button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    section_texts = {
        "help_search": (
            "🔍 <b>Manga Search & Reader Guide</b>\n\n"
            "• <code>/manga &lt;name&gt;</code> — Search across all 136+ manhwa\n"
            "• <b>Inline Search:</b> Type <code>@Galactic_Update_bot &lt;query&gt;</code> in any chat!\n"
            "• <b>Web Mini App:</b> Tap <code>/web</code> for high-speed online reading & PDF streaming!\n"
            "• <b>Groups:</b> Type the name directly when text mode is enabled (/setmode text)."
        ),
        "help_bookmarks": (
            "📌 <b>Smart Bookmark System</b>\n\n"
            "• <code>/bookmark &lt;manga&gt; &lt;chapter&gt;</code> — Save your reading chapter\n"
            "• <code>/mybookmarks</code> — View all saved bookmarks with 1-tap jump buttons\n"
            "• <code>/clearbookmarks</code> — Remove all saved bookmarks\n"
            "• You can also bookmark with 1 tap directly inside the Web Reader!"
        ),
        "help_lists": (
            "📚 <b>Reading Shelves & Tracker</b>\n\n"
            "• <code>/read</code> — View all manga you have read\n"
            "• <code>/fav</code> — View your favorite manga collection\n"
            "• <code>/completed</code> — Finished reading list\n"
            "• <code>/hold</code> & <code>/drop</code> — Paused and dropped titles\n"
            "• <code>/mylist</code> — Complete overview of your manga universe!"
        ),
        "help_requests": (
            "📨 <b>Manga Request System</b>\n\n"
            "• Send: <code>/request &lt;name&gt;</code>, <code>#request &lt;name&gt;</code>, or <code>request &lt;name&gt;</code>\n"
            "• <b>Instant Links:</b> If the manga is already available, the bot gives you the direct read link immediately!\n"
            "• <b>Admin Review:</b> Admins review requests and notify you directly in DM when approved!"
        ),
        "help_recommend": (
            "🌟 <b>Recommendations System</b>\n\n"
            "• <code>/recommend</code> — Discovers top trending manga personalized to your favorite genres!"
        ),
        "help_leaderboard": (
            "🥇 <b>Leaderboards & Ratings</b>\n\n"
            "• <code>/leaderboard</code> — Top reader rankings by chapters read 🏆\n"
            "• <code>/toprated</code> — Highest rated manga by community reviews ⭐\n"
            "• Rate any manga (1-5★) directly in the bot or Web App!"
        ),
        "help_admin": (
            "🛠 <b>Admin & Sudo Management</b>\n\n"
            "• <code>/scanallchannels</code> — High-speed MTProto past PDF scanner 🛰️\n"
            "• <code>/syncchapters</code> — Auto-sync chapter numbers\n"
            "• <code>/add &lt;channel_id&gt; &lt;name&gt;</code> — Add new manga channel\n"
            "• <code>/requestlist</code> — Review pending requests\n"
            "• <code>/replyreq &lt;user_id&gt; &lt;msg&gt;</code> — DM a user directly\n"
            "• <code>/broadcast</code> & <code>/dmbroadcast</code> — Global announcements\n"
            "• <code>/sudo</code> — List all active bot admins"
        ),
        "help_stats": (
            "📊 <b>Bot Statistics</b>\n\n"
            "• <code>/stats</code> — View total manga titles, chapters, registered users, and active groups!"
        ),
    }

    text = section_texts.get(query.data, "❓ Unknown help section.")
    back_button = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Main Help", callback_data="help_main"),
         InlineKeyboardButton("🚀 Launch Web App", web_app=WebAppInfo(url=f"{WEB_APP_URL}/web"))]
    ])

    if query.data == "help_main":
        help_cmd(update, context)
    else:
        try:
            query.edit_message_text(text=text, parse_mode="HTML", reply_markup=back_button)
        except Exception:
            try:
                query.edit_message_caption(caption=text, parse_mode="HTML", reply_markup=back_button)
            except Exception:
                pass
