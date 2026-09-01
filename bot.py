import sys
import types

# 🛠️ Python 3.12 / 3.13 pkg_resources compatibility shim for APScheduler
try:
    import pkg_resources
except ImportError:
    pr = types.ModuleType("pkg_resources")
    pr.get_distribution = lambda name: types.SimpleNamespace(version="3.6.3")
    pr.DistributionNotFound = Exception
    sys.modules["pkg_resources"] = pr

import logging
import threading
import time
from flask import Flask
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    InlineQueryHandler,
    ChatMemberHandler,
    CallbackContext,
)
try:
    from telegram.ext import Filters
except ImportError:
    from telegram.ext import filters as Filters
from config import BOT_TOKEN

# 💫 Core Handlers
from start_handler import start_cmd, help_cmd, help_button_handler, guide_cmd, guide_page_callback
from profile_handler import profile_cmd
from stats_handler import stats_cmd
from ping_handler import ping_cmd
from mode_handler import set_mode_cmd
from leaderboard_handler import leaderboard_cmd, toprated_cmd
from recommend_handler import recommend_cmd
from listmanga_handler import register_listmanga_handlers

# 🌐 Web Mini App Handlers
from web_handlers import web_cmd, webprofile_cmd, webhub_cmd
from web_app import register_web_routes

# 🔧 Admin Handlers
from admin_handlers import (
    removemanga_cmd,
    editmanga_cmd,
    set_chapters_cmd,
    syncchapters_cmd,
    addadmins_cmd,
    removeadmins_cmd,
    sudo_cmd,
    handle_forwarded_chapter,
    scanallchannels_cmd,
    uu_cmd,
    uu_page_callback,
    adminhelp_cmd,
    adminhelp_page_callback,
)
from database import auto_sync_all_chapters
from addmanga_handler import add_manga_cmd
from broadcast_handler import broadcast_cmd, delete_broadcast_cmd, bdst_cmd
from dmbroadcast_handler import dmbroadcast_cmd, delete_dmbroadcast_cmd
from delete_forwarded_handler import delete_forwarded_cmd

# 📦 Manga & Channel Handlers
from channel_handler import add_channel_cmd, handle_channel_post, handle_image, unpost_cmd, buffer_flusher
from channel_logger import chat_member_update
from channel_refresh import refresh_channels_cmd
from channel_check import check_channels_cmd
from manga_search import search_by_text_if_enabled, search_by_command

# 📚 Bookmark System
from bookmark_handler import (
    bookmark_cmd,
    mybookmarks_cmd,
    clearbookmarks_cmd,
    handle_bookmark_buttons,
)

# 📝 User Lists
from user_lists_handler import (
    readlist_cmd,
    favorites_cmd,
    completed_cmd,
    mylist_cmd,
    read_cmd,
    fav_cmd,
    hold_cmd,
    drop_cmd,
    currentlyreading_cmd,
    myhub_cmd,
    hub_cmd,
)

# 🔘 Callbacks
from callbacks import handle_status_buttons, select_manga_callback

# 📨 Requests
from request_handler import (
    request_manga,
    request_list,
    handle_request_callbacks,
    replyreq_cmd,
)

# 🔁 Inline Systems
from inline_handler import inline_query

# 🪵 Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

bot_instance = None


def get_bot():
    return bot_instance


# 🚀 Bot launch function
def main():
    global bot_instance
    # Use 8 concurrent workers for maximum speed and throughput
    updater = Updater(BOT_TOKEN, use_context=True, workers=8)
    bot_instance = updater.bot
    dp = updater.dispatcher

    # Start chapter buffer flusher in background
    threading.Thread(target=buffer_flusher, args=(updater.bot,), daemon=True, name="BufferFlusher").start()

    # Automatically sync manga chapter counts on startup in background
    threading.Thread(target=auto_sync_all_chapters, daemon=True, name="AutoChapterSync").start()

    # Register list manga pagination handlers
    register_listmanga_handlers(dp)

    # 🌐 Web Mini App Commands
    dp.add_handler(CommandHandler("web", web_cmd))
    dp.add_handler(CommandHandler("mangaweb", web_cmd))
    dp.add_handler(CommandHandler("webprofile", webprofile_cmd))
    dp.add_handler(CommandHandler("webhub", webhub_cmd))

    # ✅ Basic User Commands
    dp.add_handler(CommandHandler("start", start_cmd))
    dp.add_handler(CommandHandler("help", help_cmd))
    dp.add_handler(CommandHandler("guide", guide_cmd))
    dp.add_handler(CommandHandler("profile", profile_cmd))
    dp.add_handler(CommandHandler("stats", stats_cmd))
    dp.add_handler(CommandHandler("ping", ping_cmd))
    dp.add_handler(CommandHandler("recommend", recommend_cmd))
    dp.add_handler(CommandHandler("leaderboard", leaderboard_cmd))
    dp.add_handler(CommandHandler("toprated", toprated_cmd))
    dp.add_handler(CommandHandler(["manga", "manhwa", "manhua"], search_by_command))

    # 🛠 Admin Commands
    dp.add_handler(CommandHandler("adminhelp", adminhelp_cmd))
    dp.add_handler(CommandHandler("add", add_channel_cmd))
    dp.add_handler(CommandHandler("addmanga", add_manga_cmd))
    dp.add_handler(CommandHandler("unpost", unpost_cmd))
    dp.add_handler(CommandHandler("setmode", set_mode_cmd))
    dp.add_handler(CommandHandler("removemanga", removemanga_cmd))
    dp.add_handler(CommandHandler("editmanga", editmanga_cmd))
    dp.add_handler(CommandHandler("setchapters", set_chapters_cmd))
    dp.add_handler(CommandHandler("syncchapters", syncchapters_cmd))
    dp.add_handler(CommandHandler("autochapters", syncchapters_cmd))
    dp.add_handler(CommandHandler("scanallchannels", scanallchannels_cmd))
    dp.add_handler(CommandHandler("addadmins", addadmins_cmd))
    dp.add_handler(CommandHandler("removeadmins", removeadmins_cmd))
    dp.add_handler(CommandHandler("sudo", sudo_cmd))
    dp.add_handler(CommandHandler("broadcast", broadcast_cmd))
    dp.add_handler(CommandHandler("delete_broadcast", delete_broadcast_cmd))
    dp.add_handler(CommandHandler("bdst", bdst_cmd))
    dp.add_handler(CommandHandler("uu", uu_cmd))
    dp.add_handler(CommandHandler("delete_forwarded", delete_forwarded_cmd))
    dp.add_handler(CommandHandler("dmbroadcast", dmbroadcast_cmd))
    dp.add_handler(CommandHandler("delete_dmbroadcast", delete_dmbroadcast_cmd))

    # 📨 Manga Requests & Direct Messaging
    dp.add_handler(CommandHandler("request", request_manga))
    dp.add_handler(CommandHandler("requestlist", request_list))
    dp.add_handler(CommandHandler("replyreq", replyreq_cmd))
    dp.add_handler(CommandHandler("dm", replyreq_cmd))
    dp.add_handler(CommandHandler("reply", replyreq_cmd))
    dp.add_handler(CommandHandler("senddm", replyreq_cmd))
    dp.add_handler(CommandHandler("msg", replyreq_cmd))

    # 📚 User List Commands
    dp.add_handler(CommandHandler("myhub", myhub_cmd))
    dp.add_handler(CommandHandler("hub", hub_cmd))
    dp.add_handler(CommandHandler("read", read_cmd))
    dp.add_handler(CommandHandler("readlist", readlist_cmd))
    dp.add_handler(CommandHandler("fav", fav_cmd))
    dp.add_handler(CommandHandler("favorites", favorites_cmd))
    dp.add_handler(CommandHandler("completed", completed_cmd))
    dp.add_handler(CommandHandler("drop", drop_cmd))
    dp.add_handler(CommandHandler("hold", hold_cmd))
    dp.add_handler(CommandHandler("currentlyreading", currentlyreading_cmd))
    dp.add_handler(CommandHandler("mylist", mylist_cmd))

    # 🔖 Bookmarks
    dp.add_handler(CommandHandler("bookmark", bookmark_cmd))
    dp.add_handler(CommandHandler("mybookmarks", mybookmarks_cmd))
    dp.add_handler(CommandHandler("clearbookmarks", clearbookmarks_cmd))

    # 🔁 Callback Handlers
    dp.add_handler(CallbackQueryHandler(help_button_handler, pattern="^help_"))
    dp.add_handler(CallbackQueryHandler(handle_bookmark_buttons, pattern="^bm_"))
    dp.add_handler(CallbackQueryHandler(handle_status_buttons, pattern="^(read|unread|fav|unfav|complete|uncomplete|drop|undrop|hold|unhold|view|showrate|setrate|subtoggle|hub_)"))
    dp.add_handler(CallbackQueryHandler(handle_request_callbacks, pattern="^req_"))
    dp.add_handler(CallbackQueryHandler(select_manga_callback, pattern=r"^select_"))
    dp.add_handler(CallbackQueryHandler(uu_page_callback, pattern=r"^uu_page_\d+$"))
    dp.add_handler(CallbackQueryHandler(guide_page_callback, pattern=r"^guide_page_\d+$"))
    dp.add_handler(CallbackQueryHandler(adminhelp_page_callback, pattern=r"^adminhelp_page_\d+$"))

    # 🔍 Inline Search & Group/DM Text Search
    dp.add_handler(InlineQueryHandler(inline_query))
    dp.add_handler(MessageHandler(Filters.text & (~Filters.command), search_by_text_if_enabled))

    # 🖼 Media/Posts & Chapter Indexer
    dp.add_handler(MessageHandler(Filters.photo, handle_image))
    dp.add_handler(MessageHandler(Filters.document & Filters.chat_type.private, handle_forwarded_chapter))
    dp.add_handler(MessageHandler(Filters.update.channel_posts, handle_channel_post))

    # 👥 Chat Events
    dp.add_handler(ChatMemberHandler(chat_member_update, ChatMemberHandler.MY_CHAT_MEMBER))

    # 🔄 Maintenance
    dp.add_handler(CommandHandler("refreshchannels", refresh_channels_cmd))
    dp.add_handler(CommandHandler("checkchannels", check_channels_cmd))

    # Global error handler
    def error_handler(update: object, context: CallbackContext) -> None:
        logger.warning(f"Handled exception: {context.error}")

    dp.add_error_handler(error_handler)

    # Register Telegram Bot Command Menu (Users & Admins)
    try:
        from telegram import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
        from database import get_all_sudo
        from config import BOT_OWNER_ID

        user_cmds = [
            BotCommand("start", "🚀 Start Bot & Mini App"),
            BotCommand("myhub", "🛸 Personal Reading Hub"),
            BotCommand("webhub", "🌌 Web Reading Hub & Shelves"),
            BotCommand("web", "🌐 Open Manga Catalog & Live Reader"),
            BotCommand("webprofile", "👤 Visual Reading Profile"),
            BotCommand("manga", "🔍 Search 136+ Manga & Manhwa"),
            BotCommand("request", "📨 Request Manga / Manhwa"),
            BotCommand("bookmark", "📌 Save Reading Progress"),
            BotCommand("mybookmarks", "🔖 View Saved Bookmarks"),
            BotCommand("read", "📖 Your Read Manga List"),
            BotCommand("fav", "❤️ Your Favorite Manga"),
            BotCommand("toprated", "⭐ Top Rated Manga"),
            BotCommand("leaderboard", "🏆 Reader Leaderboard"),
            BotCommand("help", "📖 Complete Command Guide")
        ]

        admin_cmds = [
            BotCommand("start", "🚀 Start Bot & Mini App"),
            BotCommand("myhub", "🛸 Personal Reading Hub"),
            BotCommand("webhub", "🌌 Web Reading Hub & Shelves"),
            BotCommand("web", "🌐 Manga Catalog & Live Reader"),
            BotCommand("webprofile", "👤 Visual Reading Profile"),
            BotCommand("manga", "🔍 Search Manga"),
            BotCommand("scanallchannels", "🛰️ Scan Past Channel PDFs"),
            BotCommand("syncchapters", "🔄 Auto-Sync Chapter Counts"),
            BotCommand("add", "➕ Register New Manga Channel"),
            BotCommand("requestlist", "📋 Review User Requests"),
            BotCommand("replyreq", "✉️ Direct DM Reply to User"),
            BotCommand("broadcast", "📢 Channel Broadcast"),
            BotCommand("dmbroadcast", "📬 DM Broadcast to Users"),
            BotCommand("stats", "📊 Bot Statistics"),
            BotCommand("sudo", "🛡️ List Sudo Admins"),
            BotCommand("help", "📖 Help & Guide")
        ]

        # 1. Set default command menu for all users
        updater.bot.set_my_commands(user_cmds, scope=BotCommandScopeDefault())

        # 2. Set exclusive admin command menu for Owner and Sudo admins
        all_admins = set(get_all_sudo() or [])
        all_admins.add(BOT_OWNER_ID)

        for admin_id in all_admins:
            try:
                updater.bot.set_my_commands(admin_cmds, scope=BotCommandScopeChat(chat_id=admin_id))
            except Exception as e:
                logger.debug(f"Could not set admin commands for {admin_id}: {e}")

        logger.info("✅ Telegram Bot Command Menu successfully updated for Users & Admins!")
    except Exception as e:
        logger.warning(f"Could not update Telegram Bot Command Menu: {e}")

    logger.info("🤖 Galactic Manga Bot initialized with PTB v13.15 & 8 worker threads! 🛸🚀")
    updater.start_polling(drop_pending_updates=True)
    updater.idle()


# 🌐 Flask server for Render/Koyeb keep-alive & Web Mini App
app = Flask(__name__)
register_web_routes(app, get_bot)

@app.route("/")
def home():
    return "Galactic Bot is alive and running smoothly! 🌌🚀 Visit /web for Manga Mini App."

def run_flask():
    app.run(host="0.0.0.0", port=10000, use_reloader=False)

if __name__ == "__main__":
    # Start Flask Web Mini App in background daemon thread
    flask_thread = threading.Thread(target=run_flask, name="FlaskThread", daemon=True)
    flask_thread.start()

    # Run Telegram Bot polling on Main Thread (handles OS signals & PTB idle cleanly)
    main()
