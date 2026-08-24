import html
import uuid
import logging
from telegram import Update
from telegram.ext import CallbackContext
from database import set_manga_info, is_sudo, manga_col
from config import LOG_CHANNEL_ID, BOT_OWNER_ID

logger = logging.getLogger(__name__)


def is_admin(user_id: int):
    return user_id == BOT_OWNER_ID or is_sudo(user_id)


def log_to_channel(context: CallbackContext, text: str):
    try:
        context.bot.send_message(chat_id=LOG_CHANNEL_ID, text=text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        logger.warning(f"⚠️ Failed to log to channel: {e}")


# ➕ /addmanga <name> | <t.me/link> (Reply to image)
def add_manga_cmd(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = user.id

    if not is_admin(user_id):
        update.message.reply_text("🚫 You are not allowed to use this command.")
        return

    if not context.args:
        update.message.reply_text(
            "📝 Usage:\nReply to an image with:\n<code>/addmanga &lt;name&gt; | &lt;t.me/link&gt;</code>",
            parse_mode="HTML"
        )
        return

    reply = update.message.reply_to_message
    if not reply or not reply.photo:
        update.message.reply_text("❌ You must reply to a manga cover photo.")
        return

    raw_args = " ".join(context.args).strip()
    if "|" in raw_args:
        parts = [p.strip() for p in raw_args.split("|", 1)]
        name, link = parts[0], parts[1]
    else:
        parts = raw_args.rsplit(" ", 1)
        if len(parts) < 2:
            update.message.reply_text("❌ Usage: <code>/addmanga &lt;name&gt; | &lt;t.me/link&gt;</code>", parse_mode="HTML")
            return
        name, link = parts[0].strip(), parts[1].strip()

    photo = reply.photo[-1]
    image_file_id = photo.file_id

    try:
        # Generate custom unique channel ID if no channel bound
        channel_id = int(str(uuid.uuid4().int)[:10])
        set_manga_info(channel_id=channel_id, name=name, link=link, image=image_file_id)
        update.message.reply_text(f"✅ Manga <b>{html.escape(name)}</b> added successfully!", parse_mode="HTML")

        log_text = (
            f"🆕 <b>New Manga Added</b>\n"
            f"👤 By: <a href='tg://user?id={user.id}'>{html.escape(user.full_name)}</a>\n"
            f"🆔 ID: <code>{user.id}</code>\n"
            f"📚 Name: <b>{html.escape(name)}</b>\n"
            f"🔗 Link: <code>{html.escape(link)}</code>"
        )
        log_to_channel(context, log_text)

    except Exception as e:
        logger.exception("❌ Failed to add manga")
        update.message.reply_text(f"❌ Error: {e}")
