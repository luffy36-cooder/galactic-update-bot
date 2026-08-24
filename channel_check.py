import time
import logging
from telegram import Update
from telegram.ext import CallbackContext
from database import is_sudo, channels_col
from config import BOT_OWNER_ID

logger = logging.getLogger(__name__)


# ✅ Auto-checks all channel IDs from DB
def check_channels_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not (user_id == BOT_OWNER_ID or is_sudo(user_id)):
        update.message.reply_text("⛔ Only sudo users can run this command.")
        return

    channel_ids = channels_col.distinct("channel_id")
    total_checked = 0
    admin_count = 0
    failed = 0

    progress_msg = update.message.reply_text(f"🛰️ Scanning {len(channel_ids)} known channels... Please wait.")

    for cid in channel_ids:
        try:
            time.sleep(0.05)
            member = context.bot.get_chat_member(cid, context.bot.id)
            if member.status in ["administrator", "creator"]:
                admin_count += 1
            else:
                failed += 1
            total_checked += 1
        except Exception as e:
            failed += 1
            logger.warning(f"❌ Error checking channel {cid}: {e}")

    try:
        progress_msg.edit_text(
            f"<b>🔍 Channel Check Complete</b>\n\n"
            f"✅ Bot is Admin in: <b>{admin_count}</b> chats\n"
            f"📊 Total Checked: <b>{total_checked}</b>\n"
            f"❌ Inaccessible / Left: <b>{failed}</b>\n\n"
            f"<i>From database-tracked channels</i>",
            parse_mode="HTML"
        )
    except Exception:
        update.message.reply_text(
            f"Admin in: {admin_count}/{total_checked} channels. Failed: {failed}"
        )
