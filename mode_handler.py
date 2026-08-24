# mode_handler.py

from telegram import Update
from telegram.ext import CallbackContext
from database import set_group_mode
import logging

logger = logging.getLogger(__name__)

def set_mode_cmd(update: Update, context: CallbackContext):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in ["group", "supergroup"]:
         update.message.reply_text("❌ This command can only be used in groups.")
         return

    member =  context.bot.get_chat_member(chat.id, user.id)
    if not (member.status in ["administrator", "creator"]):
        update.message.reply_text("❌ You must be a group admin to change mode.")
        return

    if not context.args:
         update.message.reply_text("Usage: /setmode <text|command>")
         return

    mode = context.args[0].lower()
    if mode not in ["text", "command"]:
         update.message.reply_text("❌ Invalid mode. Use 'text' or 'command'.")
         return

    set_group_mode(chat.id, mode)
    update.message.reply_text(f"✅ Search mode set to: <b>{mode}</b>", parse_mode="HTML")
