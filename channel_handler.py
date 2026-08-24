import logging
import re
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext

from config import BOT_OWNER_ID, UPDATE_CHANNEL_ID, LOG_CHANNEL_ID
from database import (
    is_sudo,
    add_channel,
    get_all_channels,
    get_manga_by_id,
    update_manga_image,
    set_manga_info,
    was_chapter_posted,
    mark_chapter_posted,
    unmark_chapter_posted,
)

logger = logging.getLogger(__name__)
BOT_START_TIME = datetime.now(timezone.utc)
waiting_for_image = {}
channel_buffers = defaultdict(list)
last_post_time = {}

# -------------------------
# Logging helper
# -------------------------
def log_to_channel(context: CallbackContext, text):
    try:
        context.bot.send_message(
            chat_id=LOG_CHANNEL_ID,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.warning(f"⚠️ Logging failed: {e}")

# -------------------------
# Helpers
# -------------------------
def extract_chapter_number(text: str):
    match = re.search(r'\d{1,4}', text)
    return int(match.group()) if match else None

def is_admin(user_id: int):
    return user_id == BOT_OWNER_ID or is_sudo(user_id)

def build_post_link(channel_id: int, msg_id: int):
    """Build a Telegram channel post link."""
    if str(channel_id).startswith("-100"):
        return f"https://t.me/c/{str(channel_id)[4:]}/{msg_id}"
    return "Unavailable"

# -------------------------
# /add command
# -------------------------
def add_channel_cmd(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = user.id

    if not is_admin(user_id):
        return update.message.reply_text("❌ You are not allowed to use this command.")

    if len(context.args) < 2:
        return update.message.reply_text("📌 Usage: /add <channel_id> <manga name>")

    try:
        channel_id = int(context.args[0])
        manga_name = " ".join(context.args[1:]).strip()

        # Add channel to DB
        add_channel(channel_id)
        chat = context.bot.get_chat(channel_id)
        title = chat.title or manga_name

        # Get invite link
        if chat.username:
            link = f"https://t.me/{chat.username}"
        else:
            invite = context.bot.create_chat_invite_link(channel_id)
            link = invite.invite_link

        set_manga_info(channel_id, title, link, image=None)
        waiting_for_image[user_id] = channel_id

        update.message.reply_text(
            f"✅ Channel '{title}' added.\n🔗 Invite Link: {link}\n📸 Now send a manga image to save for '{manga_name}'!"
        )

        # Logging
        user_link = f"<a href='tg://user?id={user.id}'>{user.full_name}</a>"
        username = f"@{user.username}" if user.username else "No username"
        log_text = (
            f"📅 <b>New Channel Added</b>\n"
            f"👤 By: {user_link} ({username})\n"
            f"🆔 User ID: <code>{user.id}</code>\n"
            f"📚 Manga Title: <b>{title}</b>\n"
            f"🛡️ Channel ID: <code>{channel_id}</code>\n"
            f"🔗 Link: <code>{link}</code>"
        )
        log_to_channel(context, log_text)

    except Exception as e:
        logger.exception("Failed to add channel")
        update.message.reply_text(f"❌ Error: {e}")

# -------------------------
# Handle image
# -------------------------
def handle_image(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id not in waiting_for_image:
        return

    if not update.message.photo:
        return update.message.reply_text("❌ Please send a valid photo.")

    channel_id = waiting_for_image.pop(user_id)
    photo = update.message.photo[-1]
    update_manga_image(channel_id, photo.file_id)

    update.message.reply_text("✅ Manga image saved successfully.")

# -------------------------
# Handle new PDF posts in manga channel
# -------------------------
def handle_channel_post(update: Update, context: CallbackContext):
    message = update.channel_post
    channel_id = update.effective_chat.id

    if message.date < BOT_START_TIME:
        return logger.info("📟 Skipped old message")

    if channel_id not in get_all_channels():
        return logger.info("❌ Channel not registered")

    doc = message.document
    if not doc or not doc.file_name.endswith(".pdf"):
        return logger.info("❌ Not a valid manga PDF")

    chapter = extract_chapter_number(doc.file_name)
    if not chapter:
        return logger.info(f"❌ No chapter number found in {doc.file_name}")

    if was_chapter_posted(channel_id, chapter):
        return logger.info(f"🔁 Chapter {chapter} already posted")

    manga_info = get_manga_by_id(channel_id)
    title = manga_info.get("name", "Manga")
    image = manga_info.get("image")
    invite_link = manga_info.get("channel_link")  # ✅ Use invite link for Read button
    post_link = build_post_link(channel_id, message.message_id)  # For chapter number

    caption = f"📚 New chapter of <b>{title}</b>\n📖 <a href='{post_link}'>Chapter {chapter}</a>"
    buttons = InlineKeyboardMarkup([[InlineKeyboardButton("📖 Read", url=invite_link)]])

    # Buffer it
    channel_buffers[channel_id].append((chapter, caption, image, buttons, invite_link, post_link))
    last_post_time[channel_id] = time.time()
    logger.info(f"🕓 Chapter {chapter} buffered.")

# -------------------------
# Buffer flusher
# -------------------------
# -------------------------
# Buffer flusher
# -------------------------
def buffer_flusher(bot):
    while True:
        now = time.time()
        for channel_id in list(channel_buffers.keys()):
            last_time = last_post_time.get(channel_id, 0)
            if now - last_time >= 10 and channel_buffers[channel_id]:
                # Sort chapters by number
                chapters_to_post = sorted(channel_buffers[channel_id], key=lambda x: x[0])
                channel_buffers[channel_id].clear()

                chapter_numbers = [c[0] for c in chapters_to_post]
                min_chap = chapter_numbers[0]
                max_chap = chapter_numbers[-1]

                # Use last chapter's image and invite link for Read button
                _, _, image, _, invite_link, first_post_link = chapters_to_post[-1]

                # Get manga title
                manga_info = get_manga_by_id(channel_id)
                manga_title = manga_info.get("name", "Manga")

                # Build chapter line
                if min_chap == max_chap:
                    chapter_line = f"📖 <a href='{first_post_link}'>Chapter {min_chap}</a>"
                else:
                    chapter_line = f"📖 Chapters {min_chap}–{max_chap}"  # Only first chapter hyperlinked

                # Full caption
                caption = f"📚 New chapter(s) of <b>{manga_title}</b>\n{chapter_line}"
                read_button = InlineKeyboardMarkup([[InlineKeyboardButton("📖 Read", url=invite_link)]])

                try:
                    if image:
                        bot.send_photo(
                            chat_id=UPDATE_CHANNEL_ID,
                            photo=image,
                            caption=caption,
                            parse_mode="HTML",
                            reply_markup=read_button
                        )
                    else:
                        bot.send_message(
                            chat_id=UPDATE_CHANNEL_ID,
                            text=caption,
                            parse_mode="HTML",
                            reply_markup=read_button
                        )

                    # Mark all chapters as posted
                    for chapter, _, _, _, _, _ in chapters_to_post:
                        mark_chapter_posted(channel_id, chapter)
                        logger.info(f"✅ Chapter {chapter} posted and marked.")

                except Exception as e:
                    logger.exception(f"❌ Failed to post chapters {min_chap}-{max_chap}")

        time.sleep(5)


# -------------------------
# /unpost command
# -------------------------
def unpost_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return update.message.reply_text("❌ No permission.")

    if len(context.args) != 2:
        return update.message.reply_text("Usage: /unpost <channel_id> <chapter_number>")

    try:
        channel_id = int(context.args[0])
        chapter = int(context.args[1])
        unmark_chapter_posted(channel_id, chapter)
        update.message.reply_text(f"✅ Chapter {chapter} unmarked for channel {channel_id}.")
    except Exception as e:
        logger.exception("❌ Failed to unpost")
        update.message.reply_text(f"❌ Error: {e}")
