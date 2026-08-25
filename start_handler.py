import os
import random
import json
import html
import logging
from datetime import datetime
from pytz import timezone
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, InputMediaPhoto
from telegram.ext import CallbackContext
from config import LOG_CHANNEL_ID, WEB_APP_URL

logger = logging.getLogger(__name__)

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
    if update.effective_user:
        u = update.effective_user
        from database import save_bot_user
        save_bot_user(u.id, u.first_name, u.last_name, u.username)

    if context.args:
        arg = context.args[0].lower()
        if arg in ["hub", "myhub"]:
            from user_lists_handler import myhub_cmd
            return myhub_cmd(update, context)
        elif arg == "profile":
            from profile_handler import profile_cmd
            return profile_cmd(update, context)
        elif arg in ["bookmarks", "mybookmarks"]:
            from bookmark_handler import mybookmarks_cmd
            return mybookmarks_cmd(update, context)
        elif arg in ["webhub", "hubweb"]:
            from web_handlers import webhub_cmd
            return webhub_cmd(update, context)
        elif arg == "web":
            from web_handlers import web_cmd
            return web_cmd(update, context)
        elif arg == "webprofile":
            from web_handlers import webprofile_cmd
            return webprofile_cmd(update, context)
        elif arg == "request":
            from request_handler import request_manga
            return request_manga(update, context)
        elif arg in ["read", "readlist"]:
            from user_lists_handler import read_cmd
            return read_cmd(update, context)
        elif arg in ["fav", "favorites"]:
            from user_lists_handler import fav_cmd
            return fav_cmd(update, context)
        elif arg.startswith("read_") or arg.startswith("reader_"):
            try:
                parts = arg.split("_")
                cid = int(parts[1])
                ch = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
                from database import get_manga_by_id
                manga = get_manga_by_id(cid)
                name = html.escape(manga.get("name", "Manga").title()) if manga else "Manga"
                channel_link = (manga.get("channel_link") or f"https://t.me/c/{str(cid)[4:]}/1") if manga else "https://t.me"
                read_btn = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"📖 Launch Web Reader (Ch. {ch})", web_app=WebAppInfo(url=f"{WEB_APP_URL}/reader?channel_id={cid}&ch={ch}"))],
                    [
                        InlineKeyboardButton("🛸 Web Hub", web_app=WebAppInfo(url=f"{WEB_APP_URL}/webhub")),
                        InlineKeyboardButton("📖 Channel Post", url=channel_link)
                    ]
                ])
                text = (
                    f"📖 <b>{name} — Chapter {ch}</b>\n\n"
                    f"<i>Tap below to open the Web Reader Mini App directly inside Telegram:</i> 👇"
                )
                msg = update.effective_message or update.message
                if msg:
                    return msg.reply_text(text, parse_mode="HTML", reply_markup=read_btn)
            except Exception as e:
                logger.error(f"Error handling read start link: {e}")
        elif arg.startswith("manga_"):
            try:
                cid = int(arg.replace("manga_", ""))
                from database import get_manga_by_id
                from manga_search import _send_single_manga
                manga = get_manga_by_id(cid)
                if manga:
                    return _send_single_manga(update, manga)
            except Exception:
                pass

    user = update.effective_user.first_name if update.effective_user else "Senpai"
    user_id = update.effective_user.id if update.effective_user else 0
    bot_username = context.bot.username or "Galactic_Update_bot"
    is_private = update.effective_chat.type == "private" if update.effective_chat else True

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
        "🔓 Quick Commands:\n"
        "/myhub | /profile | /manga | /bookmark | /request | /help"
    )

    if is_private:
        web_btn = InlineKeyboardButton("🚀 Launch Manga Web App", web_app=WebAppInfo(url=f"{WEB_APP_URL}/web"))
        profile_btn = InlineKeyboardButton("👤 Web Profile", web_app=WebAppInfo(url=f"{WEB_APP_URL}/webprofile"))
    else:
        web_btn = InlineKeyboardButton("🚀 Launch Manga Web App", url=f"https://t.me/{bot_username}?start=web")
        profile_btn = InlineKeyboardButton("👤 Web Profile", url=f"https://t.me/{bot_username}?start=webprofile")

    buttons = InlineKeyboardMarkup([
        [web_btn],
        [
            InlineKeyboardButton("🛸 My Hub", callback_data=f"hub_back:{user_id}"),
            profile_btn
        ],
        [
            InlineKeyboardButton("🔍 Search Manga", switch_inline_query_current_chat=""),
            InlineKeyboardButton("📌 My Bookmarks", callback_data=f"bm_list_{user_id}")
        ],
        [
            InlineKeyboardButton("📚 My Reading List", callback_data="help_lists"),
            InlineKeyboardButton("🥇 Leaderboard", callback_data="help_leaderboard")
        ],
        [
            InlineKeyboardButton("📨 Request Manga", callback_data="help_requests"),
            InlineKeyboardButton("📖 Help Guide", callback_data="help_main")
        ],
        [
            InlineKeyboardButton("💬 Join Manga Galactic Group", url="https://t.me/MANGA_GALACTIC_GROUP")
        ]
    ])

    sent = False
    try:
        if update.message:
            update.message.reply_animation(
                animation="https://media.tenor.com/RHX4riDnxscAAAPo/its-time-to-read-manga.mp4",
                caption=text,
                parse_mode="HTML",
                reply_markup=buttons
            )
            sent = True
        elif update.effective_chat:
            update.effective_chat.send_animation(
                animation="https://media.tenor.com/RHX4riDnxscAAAPo/its-time-to-read-manga.mp4",
                caption=text,
                parse_mode="HTML",
                reply_markup=buttons
            )
            sent = True
    except Exception as e:
        logger.debug(f"Start animation failed, falling back to text: {e}")

    if not sent:
        if update.message:
            update.message.reply_text(text, parse_mode="HTML", reply_markup=buttons)
        elif update.effective_chat:
            update.effective_chat.send_message(text, parse_mode="HTML", reply_markup=buttons)

    # 📝 Log start command
    log_to_channel(context, f"🚀 <b>/start used</b> by <code>{user}</code> (ID: <code>{user_id}</code>)")

# /help command
def help_cmd(update: Update, context: CallbackContext):
    user = update.effective_user.first_name or "Senpai"
    user_id = update.effective_user.id
    bot_username = context.bot.username or "Galactic_Update_bot"
    is_private = update.effective_chat.type == "private" if update.effective_chat else True

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
        [
            InlineKeyboardButton("📖 Visual Guide Banner", callback_data="help_guide"),
            InlineKeyboardButton("🚀 Web App", web_app=WebAppInfo(url=f"{WEB_APP_URL}/web")) if is_private else InlineKeyboardButton("🚀 Web App", url=f"https://t.me/{bot_username}?start=web")
        ],
        [
            InlineKeyboardButton("🔍 Search Guide", callback_data="help_search"),
            InlineKeyboardButton("📌 Bookmarks Guide", callback_data="help_bookmarks")
        ],
        [
            InlineKeyboardButton("📨 Requests Guide", callback_data="help_requests"),
            InlineKeyboardButton("📚 Shelves Guide", callback_data="help_lists")
        ],
        [
            InlineKeyboardButton("🥇 Leaderboard Guide", callback_data="help_leaderboard"),
            InlineKeyboardButton("🛠 Admin Guide", callback_data="help_admin")
        ]
    ])

    if update.message:
        update.message.reply_text(text, parse_mode="HTML", reply_markup=buttons)
    elif update.effective_chat:
        update.effective_chat.send_message(text, parse_mode="HTML", reply_markup=buttons)
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
            "• <code>/scanallchannels</code> — High-speed Cloud past PDF scanner 🛰️\n"
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

    if query.data == "help_guide":
        return guide_cmd(update, context)

    text = section_texts.get(query.data, "❓ Unknown help section.")
    back_button = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Main Help", callback_data="help_main")]
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


# 📖 /guide — Sends the User Guide Banner with multi-page walkthrough
def get_user_guide_page(page: int, user_id: int, bot_username: str, is_private: bool):
    if page == 1:
        banner_path = os.path.join(os.path.dirname(__file__), "banners", "user_guide_p1.png")
        caption = (
            "🌌 <b>MANGA GALACTIC — USER GUIDE (Page 1/2)</b> 📖\n\n"
            "🌐 <b>1. In-App Webtoon Reader:</b>\n"
            "• <code>/web</code> — Open full catalog & live reader\n"
            "• <code>/webhub</code> — Visual reading shelves on web\n"
            "• <code>/webprofile</code> — Gamer rank & badges profile\n"
            "• <i>Features: Zero-delay streaming, Zen mode, Double-tap screen lock</i>\n\n"
            "🔍 <b>2. Instant Search:</b>\n"
            "• <code>/manga &lt;name&gt;</code> — Search 136+ titles with info & buttons\n"
            f"• <code>@{bot_username} &lt;name&gt;</code> — Inline poster search in any chat!\n"
            "• Direct Text Search — Type name in PM to search immediately\n\n"
            "⭐ <b>3. Discovery & Alerts:</b>\n"
            "• <code>/recommend</code> — Personalized top manga picks\n"
            "• <code>/toprated</code> — Community highest-rated manga\n"
            "• <code>/leaderboard</code> — Top reader rankings\n"
            "• 🔔 <b>Subscribe</b> — Tap on any card for instant new chapter DM alerts!"
        )
        web_btn = InlineKeyboardButton("🚀 Launch Web Reader", web_app=WebAppInfo(url=f"{WEB_APP_URL}/web")) if is_private else InlineKeyboardButton("🚀 Launch Web Reader", url=f"https://t.me/{bot_username}?start=web")
        buttons = InlineKeyboardMarkup([
            [web_btn],
            [
                InlineKeyboardButton("🔍 Search Manga", switch_inline_query_current_chat=""),
                InlineKeyboardButton("Next Page (2/2) ➡️", callback_data="guide_page_2")
            ],
            [
                InlineKeyboardButton("💬 Join Manga Galactic Group", url="https://t.me/MANGA_GALACTIC_GROUP")
            ]
        ])
    else:
        banner_path = os.path.join(os.path.dirname(__file__), "banners", "user_guide_p2.png")
        caption = (
            "🌌 <b>MANGA GALACTIC — USER GUIDE (Page 2/2)</b> 📖\n\n"
            "📌 <b>1. Smart Bookmarks System:</b>\n"
            "• <code>/bookmark &lt;name&gt; &lt;ch&gt;</code> — Save chapter (e.g. <code>/bookmark Solo Leveling 150</code>)\n"
            "• <code>/mybookmarks</code> — View saved bookmarks with 1-tap jump\n"
            "• <code>/clearbookmarks</code> — Reset saved progress\n\n"
            "🛸 <b>2. Personal Reading Hub & Shelves:</b>\n"
            "• <code>/myhub</code> (or <code>/hub</code>) — Open interactive library\n"
            "• <code>/read</code> — Completed manga list\n"
            "• <code>/fav</code> — Favorite manga list\n"
            "• <code>/currentlyreading</code> — Active reading manga\n"
            "• <code>/completed</code> | <code>/hold</code> | <code>/drop</code> — Status shelves\n"
            "• <code>/mylist</code> — Summary overview of all shelves\n\n"
            "📨 <b>3. Manga Requests & Profile:</b>\n"
            "• <code>/request &lt;name&gt;</code> — Request new manhwa (e.g. <code>/request Omniscient Reader</code>)\n"
            "• <code>/profile</code> — View your reading statistics & rank"
        )
        if is_private:
            hub_btn = InlineKeyboardButton("🛸 My Hub", callback_data=f"hub_back:{user_id}")
            bm_btn = InlineKeyboardButton("📌 My Bookmarks", callback_data=f"bm_list_{user_id}")
        else:
            hub_btn = InlineKeyboardButton("🛸 My Hub", url=f"https://t.me/{bot_username}?start=hub")
            bm_btn = InlineKeyboardButton("📌 My Bookmarks", url=f"https://t.me/{bot_username}?start=bookmarks")

        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⬅️ Prev Page (1/2)", callback_data="guide_page_1"),
                hub_btn
            ],
            [
                bm_btn,
                InlineKeyboardButton("🥇 Leaderboard", callback_data="help_leaderboard")
            ]
        ])
    return banner_path, caption, buttons


def guide_cmd(update: Update, context: CallbackContext, page: int = 1):
    user_id = update.effective_user.id if update.effective_user else 0
    bot_username = context.bot.username or "Galactic_Update_bot"
    is_private = update.effective_chat.type == "private" if update.effective_chat else True

    banner_path, caption, buttons = get_user_guide_page(page, user_id, bot_username, is_private)

    if os.path.exists(banner_path):
        with open(banner_path, "rb") as f:
            if update.message:
                update.message.reply_photo(photo=f, caption=caption, parse_mode="HTML", reply_markup=buttons)
            elif update.effective_chat:
                update.effective_chat.send_photo(photo=f, caption=caption, parse_mode="HTML", reply_markup=buttons)
    else:
        if update.message:
            update.message.reply_text(caption, parse_mode="HTML", reply_markup=buttons)
        elif update.effective_chat:
            update.effective_chat.send_message(caption, parse_mode="HTML", reply_markup=buttons)


def guide_page_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    user_id = query.from_user.id if query.from_user else 0
    bot_username = context.bot.username or "Galactic_Update_bot"
    is_private = query.message.chat.type == "private" if query.message else True

    try:
        page = int(query.data.split("_")[-1])
    except Exception:
        page = 1

    banner_path, caption, buttons = get_user_guide_page(page, user_id, bot_username, is_private)

    if os.path.exists(banner_path):
        with open(banner_path, "rb") as f:
            try:
                query.edit_message_media(
                    media=InputMediaPhoto(media=f, caption=caption, parse_mode="HTML"),
                    reply_markup=buttons
                )
            except Exception:
                try:
                    query.edit_message_caption(caption=caption, parse_mode="HTML", reply_markup=buttons)
                except Exception:
                    pass
    else:
        try:
            query.edit_message_caption(caption=caption, parse_mode="HTML", reply_markup=buttons)
        except Exception:
            pass

