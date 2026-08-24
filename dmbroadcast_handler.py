# 📁 dmbroadcast_handler.py

import time
import logging
from telegram import Update
from telegram.ext import CallbackContext
from database import db, is_sudo
from config import BOT_OWNER_ID

logger = logging.getLogger(__name__)
dmbroadcast_log_col = db["dmbroadcast_log"]


def is_admin(user_id: int):
    return user_id == BOT_OWNER_ID or is_sudo(user_id)


# 🔹 DM Broadcast Command (safe rate-limited delivery with DB persistence)
def dmbroadcast_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        update.message.reply_text("❌ You are not authorized to broadcast.")
        return

    # Must reply to a message
    if not update.message.reply_to_message:
        update.message.reply_text("❗ Reply to a message to broadcast it to all bot users in DM.")
        return

    reply_msg = update.message.reply_to_message

    # Gather unique user IDs from DB
    user_ids = set()
    for col_name in ["user_bookmarks", "user_achievements", "user_manga_status", "read_log"]:
        for doc in db[col_name].find({}, {"user_id": 1}):
            uid = doc.get("user_id")
            if uid:
                user_ids.add(uid)

    if not user_ids:
        update.message.reply_text("⚠️ No users found in database to broadcast to.")
        return

    status_msg = update.message.reply_text(f"🚀 Starting DM broadcast to {len(user_ids)} users...")

    sent_records = []
    success = 0
    failed = 0

    for uid in user_ids:
        try:
            time.sleep(0.04)  # ~25 messages/sec safe pacing
            sent_msg = context.bot.copy_message(
                chat_id=uid,
                from_chat_id=reply_msg.chat_id,
                message_id=reply_msg.message_id,
                disable_notification=False
            )
            sent_records.append({"chat_id": uid, "msg_id": sent_msg.message_id})
            success += 1
        except Exception as e:
            failed += 1

    # Persist broadcast log for reliable deletion later
    if sent_records:
        dmbroadcast_log_col.insert_one({
            "broadcast_id": update.message.message_id,
            "created_at": time.time(),
            "records": sent_records
        })

    status_msg.edit_text(
        f"✅ <b>DM Broadcast Finished!</b>\n\n"
        f"• Sent Successfully: <b>{success}</b>\n"
        f"• Failed / Blocked: <b>{failed}</b>\n"
        f"• Broadcast ID: <code>{update.message.message_id}</code>\n\n"
        f"<i>To undo, reply with /delete_dmbroadcast</i>",
        parse_mode="HTML"
    )


# 🔹 Delete DM Broadcast messages
def delete_dmbroadcast_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        update.message.reply_text("❌ Not authorized.")
        return

    # Check if replying to the broadcast command or given an ID
    broadcast_id = None
    if update.message.reply_to_message:
        broadcast_id = update.message.reply_to_message.message_id
    elif context.args and context.args[0].isdigit():
        broadcast_id = int(context.args[0])

    if not broadcast_id:
        # Check latest broadcast
        latest = dmbroadcast_log_col.find().sort("created_at", -1).limit(1)
        latest_doc = next(latest, None)
        if latest_doc:
            broadcast_id = latest_doc.get("broadcast_id")

    if not broadcast_id:
        update.message.reply_text("❗ Reply to the broadcast message or provide the Broadcast ID to delete.")
        return

    doc = dmbroadcast_log_col.find_one({"broadcast_id": broadcast_id})
    if not doc or not doc.get("records"):
        update.message.reply_text("⚠️ No broadcast record found for this ID.")
        return

    status_msg = update.message.reply_text("🗑️ Deleting broadcast messages across all DMs...")
    deleted_count = 0

    for item in doc["records"]:
        try:
            time.sleep(0.04)
            context.bot.delete_message(chat_id=item["chat_id"], message_id=item["msg_id"])
            deleted_count += 1
        except Exception:
            pass

    dmbroadcast_log_col.delete_one({"_id": doc["_id"]})
    status_msg.edit_text(f"✅ Deleted <b>{deleted_count}</b> broadcast messages from user DMs.", parse_mode="HTML")
