from database import read_log_col
from config import LOG_CHANNEL_ID
import logging
import traceback

logger = logging.getLogger(__name__)

def log_chapter_read(bot, user_id, user_name, manga_id, title, chapter_number):
    """
    Logs a chapter as read by a user.
    Also sends log message to the Telegram log channel.
    """

    try:
        # 🔍 Check if the chapter has already been logged
        existing = read_log_col.find_one({
            "user_id": user_id,
            "manga.id": manga_id,
            "chapter_number": chapter_number
        })

        if existing:
            if existing.get("deleted"):
                # ♻️ Restore soft-deleted log
                read_log_col.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {"deleted": False}}
                )
                status = "♻️ Restored"
            else:
                status = "🕒 Already Exists"
        else:
            # 🆕 Create a new read log entry
            read_log_col.insert_one({
                "user_id": user_id,
                "manga": {
                    "id": manga_id,
                    "title": title
                },
                "chapter_number": chapter_number,
                "deleted": False
            })
            status = "✅ New Read"

        # 📬 Send log to Telegram channel
        try:
             bot.send_message(
                chat_id=LOG_CHANNEL_ID,
                text=(
                    f"{status} <b>Read Log</b>\n"
                    f"👤 <code>{user_name}</code>\n"
                    f"🆔 <code>{user_id}</code>\n"
                    f"📖 <b>{title}</b>\n"
                    f"📄 Chapter <code>{chapter_number}</code>"
                ),
                parse_mode="HTML"
            )
        except Exception as log_err:
            logger.warning(f"[READ LOG ERROR] Failed to send log to channel: {log_err}")

        return status

    except Exception as e:
        logger.error(f"[READ LOG EXCEPTION] {traceback.format_exc()}")
        return "❌ Error"
