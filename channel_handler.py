import logging
import re
import threading
import time
import html
from collections import defaultdict
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import CallbackContext

from config import BOT_OWNER_ID, UPDATE_CHANNEL_ID, LOG_CHANNEL_ID, WEB_APP_URL
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
    get_manga_subscribers,
    save_chapter_file,
    db,
)

logger = logging.getLogger(__name__)
BOT_START_TIME = datetime.now(timezone.utc)
waiting_for_image = {}
channel_buffers = defaultdict(list)
last_post_time = {}

# 🎭 Static Sticker sent to update channel after each chapter post (auto-deletes previous)
UPDATE_STICKER_ID = "CAACAgUAAxkBAAIG_2qN_vCMZSjbGLA_Ml3hOjmFgf-1AAJ_JgAC0-lgVFqEBCL45B0oPQQ"

def send_update_sticker(bot):
    """Sends static update sticker to update channel and removes the previous one."""
    try:
        last_doc = db["bot_settings"].find_one({"key": "last_update_sticker"})
        if last_doc and last_doc.get("msg_id"):
            try:
                bot.delete_message(chat_id=UPDATE_CHANNEL_ID, message_id=last_doc["msg_id"])
            except Exception as e:
                logger.debug(f"Could not delete old sticker: {e}")

        sent_msg = bot.send_sticker(
            chat_id=UPDATE_CHANNEL_ID,
            sticker=UPDATE_STICKER_ID
        )
        db["bot_settings"].update_one(
            {"key": "last_update_sticker"},
            {"$set": {"msg_id": sent_msg.message_id, "updated_at": time.time()}},
            upsert=True
        )
        logger.info("✅ Update sticker sent and previous sticker cleaned up.")
    except Exception as e:
        logger.warning(f"Failed to send update sticker: {e}")


# -------------------------
# Logging helper
# -------------------------
def log_to_channel(context: CallbackContext, text: str):
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
    """Accurately extracts chapter number from various filename formats."""
    match = re.search(r'(?:ch(?:apter)?\.?\s*|c\s*)(\d+(?:\.\d+)?)', text, re.IGNORECASE)
    if match:
        try:
            return int(float(match.group(1)))
        except (ValueError, TypeError):
            pass

    match = re.search(r'\d{1,4}', text)
    return int(match.group()) if match else None


def is_admin(user_id: int):
    return user_id == BOT_OWNER_ID or is_sudo(user_id)


def build_post_link(channel_id: int, msg_id: int, invite_link: str = None):
    """Build a direct post link for public & private channels."""
    cid_str = str(channel_id)
    if cid_str.startswith("-100"):
        return f"https://t.me/c/{cid_str[4:]}/{msg_id}"
    elif cid_str.startswith("-"):
        return f"https://t.me/c/{cid_str[1:]}/{msg_id}"
    return invite_link or "https://t.me"


# -------------------------
# 🔔 Auto New Chapter DM Notification Worker
# -------------------------
def notify_subscribers_async(bot, channel_id: int, manga_title: str, min_chap: int, max_chap: int, first_post_link: str, invite_link: str, image: str = None):
    """Sends background DM alerts to all users subscribed to this manga."""
    def task():
        subscribers = get_manga_subscribers(channel_id)
        if not subscribers:
            logger.info(f"🔔 No subscribers to notify for {manga_title}")
            return

        if min_chap == max_chap:
            chap_text = f"Chapter {min_chap}"
        else:
            chap_text = f"Chapters {min_chap}–{max_chap}"

        safe_title = html.escape(manga_title)
        alert_caption = (
            f"🔔 <b>New Chapter Alert!</b> 🌌\n\n"
            f"📚 <b>{safe_title}</b>\n"
            f"📖 <a href='{first_post_link}'><b>{chap_text}</b></a> is now out! 🎉\n\n"
            f"<i>Happy reading, senpai~</i> 💕"
        )

        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("📖 Read in Channel", url=first_post_link or invite_link)]
        ])

        sent_count = 0
        for uid in subscribers:
            try:
                time.sleep(0.04)  # Rate-limit to avoid 429 FloodWait
                if image:
                    bot.send_photo(
                        chat_id=uid,
                        photo=image,
                        caption=alert_caption,
                        parse_mode="HTML",
                        reply_markup=buttons
                    )
                else:
                    bot.send_message(
                        chat_id=uid,
                        text=alert_caption,
                        parse_mode="HTML",
                        reply_markup=buttons,
                        disable_web_page_preview=False
                    )
                sent_count += 1
            except Exception as e:
                pass  # Ignore blocked users or DM restrictions

        logger.info(f"🔔 Notified {sent_count}/{len(subscribers)} subscribers for {manga_title} ({chap_text})")

    threading.Thread(target=task, daemon=True).start()


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
# Handle image upload after /add
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

    update.message.reply_text("✅ Manga cover image saved successfully.")


# -------------------------
# Handle new PDF posts in manga channel
# -------------------------
def handle_channel_post(update: Update, context: CallbackContext):
    message = update.channel_post
    if not message:
        return

    channel_id = update.effective_chat.id

    if message.date < BOT_START_TIME:
        return logger.info("📟 Skipped old message")

    if channel_id not in get_all_channels():
        return logger.info("❌ Channel not registered in bot database")

    doc = message.document
    if not doc or not doc.file_name or not doc.file_name.lower().endswith(".pdf"):
        return logger.info("❌ Post is not a PDF file")

    chapter = extract_chapter_number(doc.file_name)
    if chapter is None:
        return logger.info(f"❌ No chapter number found in {doc.file_name}")

    if was_chapter_posted(channel_id, chapter):
        return logger.info(f"🔁 Chapter {chapter} already posted before")

    manga_info = get_manga_by_id(channel_id) or {}
    image = manga_info.get("image")
    invite_link = manga_info.get("channel_link") or f"https://t.me/c/{str(channel_id)[4:]}/1"
    post_link = build_post_link(channel_id, message.message_id, invite_link)

    # Save chapter PDF file reference for Web Reader
    save_chapter_file(channel_id, chapter, doc.file_id, doc.file_name, message.message_id)

    # Buffer the chapter release: (chapter_num, msg_id, image, invite_link, post_link)
    channel_buffers[channel_id].append((chapter, message.message_id, image, invite_link, post_link))
    last_post_time[channel_id] = time.time()
    logger.info(f"🕓 Chapter {chapter} buffered for channel {channel_id} (Post Link: {post_link}).")


# -------------------------
# Buffer flusher (Aggregates single and batch chapter uploads)
# -------------------------
def buffer_flusher(bot):
    while True:
        now = time.time()
        for channel_id in list(channel_buffers.keys()):
            last_time = last_post_time.get(channel_id, 0)
            if now - last_time >= 10 and channel_buffers[channel_id]:
                # Sort chapters in ascending order
                chapters_to_post = sorted(channel_buffers[channel_id], key=lambda x: x[0])
                channel_buffers[channel_id].clear()

                first_entry = chapters_to_post[0]
                last_entry = chapters_to_post[-1]

                min_chap = first_entry[0]
                max_chap = last_entry[0]
                first_post_link = first_entry[4]

                # Use cover image and invite link
                image = last_entry[2] or first_entry[2]
                invite_link = last_entry[3] or first_entry[3]

                # Fetch manga info
                manga_info = get_manga_by_id(channel_id) or {}
                manga_title = manga_info.get("name", "Manga")

                # Build chapter line with hyperlinked first post
                if min_chap == max_chap:
                    chapter_line = f"📖 <a href='{first_post_link}'>Chapter {min_chap}</a>"
                else:
                    chapter_line = f"📖 <a href='{first_post_link}'>Chapters {min_chap}–{max_chap}</a>"

                caption = f"📚 New chapter(s) of <b>{manga_title}</b>\n{chapter_line}"
                read_button = InlineKeyboardMarkup([[InlineKeyboardButton("📖 Read Manga", url=invite_link)]])

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
                            reply_markup=read_button,
                            disable_web_page_preview=False
                        )

                    # 🎭 Send static sticker to update channel and clean previous
                    send_update_sticker(bot)

                    # Mark all chapters in this batch as posted
                    for item in chapters_to_post:
                        chap_num = item[0]
                        mark_chapter_posted(channel_id, chap_num)
                        logger.info(f"✅ Chapter {chap_num} marked as posted.")

                    # 🔔 Trigger Auto DM Notification to all subscribed users!
                    notify_subscribers_async(
                        bot,
                        channel_id=channel_id,
                        manga_title=manga_title,
                        min_chap=min_chap,
                        max_chap=max_chap,
                        first_post_link=first_post_link,
                        invite_link=invite_link,
                        image=image
                    )

                except Exception as e:
                    logger.exception(f"❌ Failed to post chapters {min_chap}–{max_chap} to update channel: {e}")

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
