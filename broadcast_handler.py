import logging
import difflib
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext
from database import get_all_channels, get_manga_by_id, broadcast_log_col, is_sudo
from config import BOT_OWNER_ID

logger = logging.getLogger(__name__)

# -------------------------
# Permission check
# -------------------------
def is_admin(user_id: int):
    return user_id == BOT_OWNER_ID or is_sudo(user_id)

# -------------------------
# /broadcast command
# -------------------------
def broadcast_cmd(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = user.id

    if not is_admin(user_id):
        return update.message.reply_text("❌ You are not allowed to use this command.")

    if not context.args and not update.message.reply_to_message:
        return update.message.reply_text(
            "📝 Usage:\n"
            "/broadcast <message>\n"
            "Or reply to a message (text/photo) with /broadcast"
        )

    # Determine message content
    text = " ".join(context.args) if context.args else None
    reply = update.message.reply_to_message

    photo = None
    caption = None
    if reply:
        if reply.photo:
            photo = reply.photo[-1].file_id
            caption = reply.caption or text
        else:
            text = reply.text or text

    if not text and not photo:
        return update.message.reply_text("❌ Nothing to broadcast.")

    # Optional inline button
    buttons = None
    if text and "button=" in text.lower():
        try:
            parts = text.split("button=")[1].split("|")
            btn_text = parts[0].strip()
            btn_url = parts[1].strip()
            buttons = InlineKeyboardMarkup([[InlineKeyboardButton(btn_text, url=btn_url)]])
            text = text.split("button=")[0].strip()
        except Exception as e:
            logger.warning(f"Failed to parse button: {e}")

    sent_count = 0
    failed_count = 0

    for channel_id in get_all_channels():
        chat_id = channel_id
        try:
            if photo:
                msg = context.bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=buttons
                )
            else:
                msg = context.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=buttons
                )

            # Log this broadcast for future deletion
            broadcast_log_col.update_one(
                {"original_msg_id": update.message.message_id},
                {"$addToSet": {"channel_msgs": {"chat_id": chat_id, "msg_id": msg.message_id}}},
                upsert=True
            )

            sent_count += 1
        except Exception as e:
            logger.warning(f"❌ Failed to send to {channel_id}: {e}")
            failed_count += 1

    update.message.reply_text(f"✅ Broadcast done!\nSent: {sent_count}\nFailed: {failed_count}")

# -------------------------
# /delete_broadcast command
# -------------------------
def delete_broadcast_cmd(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = user.id

    if not is_admin(user_id):
        return update.message.reply_text("❌ You are not allowed to use this command.")

    reply = update.message.reply_to_message
    if not reply:
        return update.message.reply_text("❌ Reply to the broadcast message you want to delete.")

    log_entry = broadcast_log_col.find_one({"original_msg_id": reply.message_id})
    if not log_entry:
        return update.message.reply_text("❌ No broadcast record found for this message.")

    deleted_count = 0
    for item in log_entry.get("channel_msgs", []):
        try:
            context.bot.delete_message(chat_id=item["chat_id"], message_id=item["msg_id"])
            deleted_count += 1
        except Exception as e:
            logger.warning(f"❌ Failed to delete msg in {item['chat_id']}: {e}")

    # Remove the log entry after deletion
    broadcast_log_col.delete_one({"_id": log_entry["_id"]})

    update.message.reply_text(f"🗑️ Broadcast deleted in {deleted_count} channels.")

