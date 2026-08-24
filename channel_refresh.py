import time
import logging
from telegram import Update
from telegram.ext import CallbackContext
from database import channels_col, is_sudo
from config import BOT_OWNER_ID

logger = logging.getLogger(__name__)


def refresh_channels_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    if not (user_id == BOT_OWNER_ID or is_sudo(user_id)):
        update.message.reply_text("⛔ Only sudo users can run this command.")
        return

    chat_ids = channels_col.distinct("channel_id")
    success, failed = 0, 0

    progress_msg = update.message.reply_text(f"🕵️‍♂️ Checking {len(chat_ids)} channels... Please wait.")

    for cid in chat_ids:
        try:
            time.sleep(0.05)  # Small pacing to avoid rate limits
            member = context.bot.get_chat_member(cid, context.bot.id)
            if member.status in ["administrator", "creator"]:
                chat = context.bot.get_chat(cid)
                name = chat.title or "Unnamed Channel"
                channels_col.update_one(
                    {"channel_id": cid},
                    {"$set": {"name": name}},
                    upsert=True
                )
                success += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            logger.warning(f"❌ Failed to refresh channel {cid}: {e}")

    try:
        progress_msg.edit_text(
            f"✅ <b>Channel Refresh Complete!</b>\n\n"
            f"• Successfully refreshed: <b>{success}</b>\n"
            f"• Inaccessible/Failed: <b>{failed}</b>\n"
            f"• Total tracked: <b>{len(chat_ids)}</b>",
            parse_mode="HTML"
        )
    except Exception:
        update.message.reply_text(
            f"✅ Refreshed: {success} | Failed: {failed}"
        )
