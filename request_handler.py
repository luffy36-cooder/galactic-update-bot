import logging
import traceback
import re
from datetime import datetime
from html import escape as quote_html
from bson import ObjectId

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

from database import is_sudo, request_col
from config import LOG_CHANNEL_ID, BOT_OWNER_ID

logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id == BOT_OWNER_ID or is_sudo(user_id)


def is_valid_manga_name(name: str) -> bool:
    return bool(re.search(r"[A-Za-z0-9]", name))


def log_to_channel(context: CallbackContext, text: str):
    try:
        context.bot.send_message(
            chat_id=LOG_CHANNEL_ID,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.warning(f"[LOG ERROR] {e}")


def request_manga(update: Update, context: CallbackContext):
    if not update.message:
        return

    user = update.effective_user
    text = update.message.text or ""

    if text.startswith("/request"):
        query = text.split(' ', 1)[1].strip() if ' ' in text else ""
    elif text.lower().startswith("#request"):
        query = text[len("#request"):].strip()
    else:
        return

    if not query or not is_valid_manga_name(query):
        update.message.reply_text("⚠️ Please enter a valid manga name using letters or numbers.")
        log_to_channel(context, f"❗ <b>Invalid Request Attempt</b> by <code>{quote_html(user.full_name)}</code> (ID: <code>{user.id}</code>) - Sent: <code>{quote_html(query)}</code>")
        return

    if len(query) > 100:
        update.message.reply_text("⚠️ Manga name too long. Please keep it under 100 characters.")
        return

    try:
        context.bot.send_message(
            chat_id=user.id,
            text="📬 Manga request received successfully! Thank you for your request. We'll do our best to upload it as soon as possible~ 💖"
        )
    except Exception:
        update.message.reply_text("⚠️ Please start the bot in private first before requesting manga!\nTap here 👉 @Galactic_Update_bot and press START!")
        log_to_channel(context, f"❌ <b>Request Blocked - Cannot DM</b>\n👤 <code>{quote_html(user.full_name)}</code>\n🆔 <code>{user.id}</code>\n📖 <b>{quote_html(query)}</b>")
        return

    existing = request_col.find_one({
        "manga_name": {"$regex": f"^{re.escape(query)}$", "$options": "i"},
        "status": "pending"
    })

    if existing:
        update.message.reply_text("⚠️ This manga has already been requested and is pending review~ 🕒")
        log_to_channel(context, f"🛑 <b>Duplicate Request Blocked</b>\n👤 <code>{quote_html(user.full_name)}</code>\n📖 <b>{quote_html(query)}</b>")
        return

    request_col.insert_one({
        "user_id": user.id,
        "username": user.full_name,
        "manga_name": query,
        "status": "pending",
        "timestamp": datetime.utcnow()
    })

    update.message.reply_text("✅ Your manga request has been submitted to the bot admin! 📬")
    log_to_channel(context, f"📥 <b>New Manga Request</b>\n👤 <code>{quote_html(user.full_name)}</code>\n🆔 <code>{user.id}</code>\n📖 <b>{quote_html(query)}</b>")


def request_list(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        update.message.reply_text("⛔ Only sudo users can access the request list.")
        return

    log_to_channel(context, f"📋 <b>Request List Accessed</b>\n👮 <code>{quote_html(update.effective_user.full_name)}</code> (ID: <code>{user_id}</code>)")

    requests = list(request_col.find({"status": "pending"}).sort("timestamp", -1))
    if not requests:
        update.message.reply_text("📭 No pending manga requests found.")
        return

    for req in requests[:15]:  # show up to 15 pending requests
        req_id = str(req.get("_id"))
        req_user_id = str(req.get("user_id"))

        if not req_id or not req_user_id:
            continue

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Complete", callback_data=f"complete_request|{req_id}|{req_user_id}"),
            InlineKeyboardButton("❌ Deny", callback_data=f"deny_request|{req_id}|{req_user_id}")
        ]])

        update.message.reply_text(
            f"📖 <b>Request:</b> {quote_html(req.get('manga_name', ''))}\n👤 <b>Requested by:</b> {quote_html(req.get('username', 'Unknown'))}",
            parse_mode="HTML",
            reply_markup=keyboard
        )


def complete_request_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    try:
        query.answer()
    except Exception as e:
        logger.warning(f"❌ query.answer failed: {e}")

    admin_user = query.from_user
    if not is_admin(admin_user.id):
        try:
            query.edit_message_text("⛔ You are not allowed to perform this action.")
        except Exception:
            pass
        return

    try:
        parts = query.data.split("|")
        if len(parts) != 3:
            raise ValueError("Expected 3 parts in callback data.")
        _, req_id_str, user_id_str = parts
        req_id = ObjectId(req_id_str)
        target_user_id = int(user_id_str)
    except Exception as e:
        logger.error(f"❌ Failed to parse callback data: {query.data} | Error: {e}")
        try:
            query.edit_message_text("⚠️ Invalid callback data received.")
        except Exception:
            pass
        return

    try:
        request_doc = request_col.find_one({"_id": req_id})
        if not request_doc:
            query.edit_message_text("⚠️ Request not found or already processed.")
            return

        request_col.update_one({"_id": req_id}, {"$set": {"status": "completed", "completed_by": admin_user.id}})
        manga_name = request_doc.get("manga_name", "Unknown")

        user_notified = False
        try:
            context.bot.send_message(
                chat_id=target_user_id,
                text=f"🎉 Your manga request for <b>{quote_html(manga_name)}</b> has been fulfilled! Happy reading 💕",
                parse_mode="HTML"
            )
            user_notified = True
        except Exception as e:
            logger.warning(f"❌ Could not notify user {target_user_id}: {e}")

        msg = f"✅ Request for <b>{quote_html(manga_name)}</b> was completed."
        if not user_notified:
            msg += " <i>(User could not be DMed)</i>"
        query.edit_message_text(msg, parse_mode="HTML")

        log_to_channel(
            context,
            f"✅ <b>Request Completed</b>\n📖 <b>{quote_html(manga_name)}</b>\n👤 User ID: <code>{target_user_id}</code>\n👮 Admin: <code>{quote_html(admin_user.full_name)}</code>"
        )

    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Error in complete_request_callback:\n{tb}")
        try:
            query.edit_message_text("❌ An error occurred while completing the request.")
        except Exception:
            pass


def deny_request_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    try:
        query.answer()
    except Exception as e:
        logger.warning(f"❌ query.answer failed: {e}")

    admin_user = query.from_user
    if not is_admin(admin_user.id):
        try:
            query.edit_message_text("⛔ You are not allowed to perform this action.")
        except Exception:
            pass
        return

    try:
        parts = query.data.split("|")
        if len(parts) != 3:
            raise ValueError("Expected 3 parts in callback data.")
        _, req_id_str, user_id_str = parts
        req_id = ObjectId(req_id_str)
        target_user_id = int(user_id_str)
    except Exception as e:
        logger.error(f"❌ Failed to parse callback data: {query.data} | Error: {e}")
        try:
            query.edit_message_text("⚠️ Invalid callback data received.")
        except Exception:
            pass
        return

    try:
        request_doc = request_col.find_one({"_id": req_id})
        if not request_doc:
            query.edit_message_text("⚠️ Request not found or already processed.")
            return

        request_col.update_one({"_id": req_id}, {"$set": {"status": "denied", "denied_by": admin_user.id}})
        manga_name = request_doc.get("manga_name", "Unknown")

        user_notified = False
        try:
            context.bot.send_message(
                chat_id=target_user_id,
                text=f"❌ Your manga request for <b>{quote_html(manga_name)}</b> could not be fulfilled at this time.",
                parse_mode="HTML"
            )
            user_notified = True
        except Exception as e:
            logger.warning(f"❌ Could not notify user {target_user_id}: {e}")

        msg = f"❌ Request for <b>{quote_html(manga_name)}</b> was denied."
        if not user_notified:
            msg += " <i>(User could not be DMed)</i>"
        query.edit_message_text(msg, parse_mode="HTML")

        log_to_channel(
            context,
            f"❌ <b>Request Denied</b>\n📖 <b>{quote_html(manga_name)}</b>\n👤 User ID: <code>{target_user_id}</code>\n👮 Admin: <code>{quote_html(admin_user.full_name)}</code>"
        )

    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Error in deny_request_callback:\n{tb}")
        try:
            query.edit_message_text("❌ An error occurred while denying the request.")
        except Exception:
            pass
