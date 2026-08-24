# 📁 delete_forwarded_handler.py
import logging
from telegram import Update
from telegram.ext import CallbackContext
from database import get_all_channels, is_sudo
from config import BOT_OWNER_ID

logger = logging.getLogger(__name__)


def is_admin(user_id: int):
    return user_id == BOT_OWNER_ID or is_sudo(user_id)


def delete_forwarded_cmd(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = user.id

    if not is_admin(user_id):
        return update.message.reply_text("❌ You are not allowed to use this command.")

    reply = update.message.reply_to_message
    if not reply:
        return update.message.reply_text("❌ Reply to the message you want to force-delete across registered channels.")

    deleted_count = 0
    failed_count = 0

    for channel_id in get_all_channels():
        try:
            context.bot.delete_message(chat_id=channel_id, message_id=reply.message_id)
            deleted_count += 1
        except Exception:
            failed_count += 1

    update.message.reply_text(f"🗑️ Force deletion attempt completed!\n• Deleted in: {deleted_count} channels\n• Inaccessible: {failed_count}")
