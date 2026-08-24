import logging
import threading
import time
from flask import Flask
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackQueryHandler,
    InlineQueryHandler,
    ChatMemberHandler,
)
from config import BOT_TOKEN

# 💫 Core Handlers
from start_handler import start_cmd, help_cmd, help_button_handler
from profile_handler import profile_cmd
from stats_handler import stats_cmd
from ping_handler import ping_cmd
from mode_handler import set_mode_cmd
from leaderboard_handler import leaderboard_cmd
from recommend_handler import recommend_cmd
from listmanga_handler import register_listmanga_handlers

# 🔧 Admin Handlers
from admin_handlers import (
    removemanga_cmd,
    editmanga_cmd,
    set_chapters_cmd,
    addadmins_cmd,
    removeadmins_cmd,
    sudo_cmd,
)
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


# 🚀 Bot launch function
def main():
    # Use 8 concurrent workers for maximum speed and throughput
    updater = Updater(BOT_TOKEN, use_context=True, workers=8)
    dp = updater.dispatcher

    # Start chapter buffer flusher in background
    threading.Thread(target=buffer_flusher, args=(updater.bot,), daemon=True, name="BufferFlusher").start()

    # Register list manga pagination handlers
    register_listmanga_handlers(dp)

    # ✅ Basic User Commands
    dp.add_handler(CommandHandler("start", start_cmd))
    dp.add_handler(CommandHandler("help", help_cmd))
    dp.add_handler(CommandHandler("profile", profile_cmd))
    dp.add_handler(CommandHandler("stats", stats_cmd))
    dp.add_handler(CommandHandler("ping", ping_cmd))
    dp.add_handler(CommandHandler("recommend", recommend_cmd))
    dp.add_handler(CommandHandler("leaderboard", leaderboard_cmd))
    dp.add_handler(CommandHandler("manga", search_by_command))

    # 🛠 Admin Commands
    dp.add_handler(CommandHandler("add", add_channel_cmd))
    dp.add_handler(CommandHandler("addmanga", add_manga_cmd))
    dp.add_handler(CommandHandler("unpost", unpost_cmd))
    dp.add_handler(CommandHandler("setmode", set_mode_cmd))
    dp.add_handler(CommandHandler("removemanga", removemanga_cmd))
    dp.add_handler(CommandHandler("editmanga", editmanga_cmd))
    dp.add_handler(CommandHandler("setchapters", set_chapters_cmd))
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
    dp.add_handler(CallbackQueryHandler(handle_status_buttons, pattern="^(read|unread|fav|unfav|complete|uncomplete|drop|undrop|hold|unhold|view)_"))
    dp.add_handler(CallbackQueryHandler(complete_request_callback, pattern="^complete_request"))
    dp.add_handler(CallbackQueryHandler(deny_request_callback, pattern="^deny_request"))
    dp.add_handler(CallbackQueryHandler(select_manga_callback, pattern=r"^select_"))

    # 🔍 Inline Search & Group Text Search
    dp.add_handler(InlineQueryHandler(inline_query))
    dp.add_handler(MessageHandler(Filters.text & Filters.chat_type.groups & (~Filters.command), search_by_text_if_enabled))
    dp.add_handler(MessageHandler(Filters.text & Filters.chat_type.private & (~Filters.command), request_manga))

    # 🖼 Media/Posts
    dp.add_handler(MessageHandler(Filters.photo, handle_image))
    dp.add_handler(MessageHandler(Filters.update.channel_posts, handle_channel_post))

    # 👥 Chat Events
    dp.add_handler(ChatMemberHandler(chat_member_update, ChatMemberHandler.MY_CHAT_MEMBER))

    # 🔄 Maintenance
    dp.add_handler(CommandHandler("refreshchannels", refresh_channels_cmd))
    dp.add_handler(CommandHandler("checkchannels", check_channels_cmd))

    logger.info("🤖 Galactic Manga Bot initialized with PTB v13.15 & 8 worker threads! 🛸🚀")
    updater.start_polling(drop_pending_updates=True)
    updater.idle()


# 🌐 Flask server for Render/Koyeb keep-alive
app = Flask(__name__)

@app.route("/")
def home():
    return "Galactic Bot is alive and running smoothly! 🌌🚀"

if __name__ == "__main__":
    threading.Thread(target=main, name="BotThread", daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
