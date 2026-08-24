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
from start_handler import start_cmd, help_cmd, help_button_handler
from profile_handler import profile_cmd
from stats_handler import stats_cmd
from ping_handler import ping_cmd
from mode_handler import set_mode_cmd
from leaderboard_handler import leaderboard_cmd, toprated_cmd
from recommend_handler import recommend_cmd
from listmanga_handler import register_listmanga_handlers

# 🌐 Web Mini App Handlers
from web_handlers import web_cmd, webprofile_cmd
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
)
from database import auto_sync_all_chapters
from addmanga_handler import add_manga_cmd
from broadcast_handler import broadcast_cmd, delete_broadcast_cmd
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
)

# 🔘 Callbacks
from callbacks import handle_status_buttons, select_manga_callback

# 📨 Requests
from request_handler import (
    request_manga,
    request_list,
    complete_request_callback,
    deny_request_callback,
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

    # ✅ Basic User Commands
    dp.add_handler(CommandHandler("start", start_cmd))
    dp.add_handler(CommandHandler("help", help_cmd))
    dp.add_handler(CommandHandler("profile", profile_cmd))
    dp.add_handler(CommandHandler("stats", stats_cmd))
    dp.add_handler(CommandHandler("ping", ping_cmd))
    dp.add_handler(CommandHandler("recommend", recommend_cmd))
    dp.add_handler(CommandHandler("leaderboard", leaderboard_cmd))
    dp.add_handler(CommandHandler("toprated", toprated_cmd))
    dp.add_handler(CommandHandler("manga", search_by_command))

    # 🛠 Admin Commands
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
    dp.add_handler(CommandHandler("delete_forwarded", delete_forwarded_cmd))
    dp.add_handler(CommandHandler("dmbroadcast", dmbroadcast_cmd))
    dp.add_handler(CommandHandler("delete_dmbroadcast", delete_dmbroadcast_cmd))

    # 📨 Manga Requests
    dp.add_handler(CommandHandler("request", request_manga))
    dp.add_handler(CommandHandler("requestlist", request_list))

    # 📚 User List Commands
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
    dp.add_handler(CallbackQueryHandler(handle_status_buttons, pattern="^(read|unread|fav|unfav|complete|uncomplete|drop|undrop|hold|unhold|view|showrate|setrate|subtoggle)_"))
    dp.add_handler(CallbackQueryHandler(complete_request_callback, pattern="^complete_request"))
    dp.add_handler(CallbackQueryHandler(deny_request_callback, pattern="^deny_request"))
    dp.add_handler(CallbackQueryHandler(select_manga_callback, pattern=r"^select_"))

    # 🔍 Inline Search & Group Text Search
    dp.add_handler(InlineQueryHandler(inline_query))
    dp.add_handler(MessageHandler(Filters.text & Filters.chat_type.groups & (~Filters.command), search_by_text_if_enabled))
    dp.add_handler(MessageHandler(Filters.text & Filters.chat_type.private & (~Filters.command), request_manga))

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
