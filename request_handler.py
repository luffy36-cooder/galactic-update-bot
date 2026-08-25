import logging
import re
import html
from datetime import datetime, timezone
from bson import ObjectId
from rapidfuzz import process, fuzz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

from database import is_sudo, get_all_sudo, request_col, get_all_manga_cached
from config import LOG_CHANNEL_ID, BOT_OWNER_ID

logger = logging.getLogger(__name__)

# State dictionary for interactive admin custom messages: {admin_id: (req_id, target_user_id, action_type)}
waiting_admin_reply = {}


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


def _sync_admin_messages(context: CallbackContext, req_doc: dict, acting_admin, action_summary: str):
    """Synchronously edits and removes action buttons from all other admins' alert messages."""
    if not req_doc:
        return
    admin_msgs = req_doc.get("admin_messages") or {}
    m_name = req_doc.get("manga_name", "Manga")
    target_uid = req_doc.get("user_id", "")
    admin_name = html.escape(acting_admin.first_name or "Admin")

    sync_text = (
        f"📨 <b>Manga Request Resolved</b> 🌌\n\n"
        f"📚 <b>Manga:</b> <code>{html.escape(m_name)}</code>\n"
        f"🆔 <b>User ID:</b> <code>{target_uid}</code>\n\n"
        f"✨ <b>Status:</b> {action_summary} by <b>{admin_name}</b>"
    )

    for aid_str, mid in admin_msgs.items():
        if int(aid_str) == acting_admin.id:
            continue
        try:
            context.bot.edit_message_text(
                chat_id=int(aid_str),
                message_id=mid,
                text=sync_text,
                parse_mode="HTML",
                reply_markup=None
            )
        except Exception:
            pass


# =========================================================
# 📨 Main Request Command & Text Handler
# Strictly requires: /request, #request, or request (case-insensitive)
# =========================================================
def request_manga(update: Update, context: CallbackContext):
    if not update.message:
        return

    # Check if admin is currently replying with a custom note to a user
    if handle_admin_reply_text(update, context):
        return

    user = update.effective_user
    text = (update.message.text or "").strip()
    if not text:
        return

    # Extract query strictly from /request, #request, or 'request <name>' (Case-Insensitive)
    text_lower = text.lower()
    query = ""
    if text_lower.startswith("/request"):
        query = text[len("/request"):].strip()
    elif text_lower.startswith("#request"):
        query = text[len("#request"):].strip()
    elif text_lower.startswith("request"):
        remainder = text[len("request"):].strip()
        if remainder.startswith(":") or remainder.startswith("-"):
            remainder = remainder[1:].strip()
        query = remainder
    else:
        # Not a request command - ignore random conversation messages
        return

    if not query or not is_valid_manga_name(query):
        update.message.reply_text(
            "⚠️ <b>Please specify the manga or manhwa title!</b>\n\n"
            "📌 <b>Usage:</b>\n"
            "• <code>/request &lt;manga name&gt;</code>\n"
            "• <code>#request &lt;manga name&gt;</code>\n"
            "• <code>request &lt;manga name&gt;</code>",
            parse_mode="HTML"
        )
        return

    if len(query) > 120:
        update.message.reply_text("⚠️ Manga name is too long. Please keep it under 120 characters.")
        return

    # 1. 🔒 Verify user has started the bot in PM (Can receive bot DMs)
    can_dm = False
    try:
        context.bot.send_chat_action(chat_id=user.id, action="typing")
        can_dm = True
    except Exception:
        can_dm = False

    if not can_dm:
        bot_username = context.bot.username or "Galactic_Update_bot"
        start_url = f"https://t.me/{bot_username}?start=req"
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Start Bot in Private", url=start_url)]])
        update.message.reply_text(
            f"❌ <b>Please start the bot in private first!</b>\n\n"
            f"Hey {user.mention_html()}, you must start the bot in private first so we can DM you when your requested manga is uploaded!",
            reply_markup=btn,
            parse_mode="HTML"
        )
        return

    # 2. 🔍 Check if Manhwa is ALREADY UPLOADED in Database
    all_manga = get_all_manga_cached()
    names = [m.get("name", "") for m in all_manga if m.get("name")]
    if names:
        match = process.extractOne(query, names, scorer=fuzz.token_sort_ratio)
        if match and match[1] >= 82:
            match_manga = next((m for m in all_manga if m.get("name") == match[0]), None)
            if match_manga:
                m_name = match_manga.get("name")
                m_cid = match_manga.get("channel_id")
                m_chaps = match_manga.get("total_chapters") or "Available"
                m_link = match_manga.get("channel_link") or (f"https://t.me/c/{str(m_cid)[4:]}/1" if m_cid else "https://t.me")

                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📖 Read in Channel", url=m_link)]
                ])

                update.message.reply_text(
                    f"🎉 <b>Great news! This manga is already uploaded!</b>\n\n"
                    f"📚 <b>{html.escape(m_name)}</b>\n"
                    f"📖 Chapters: <b>{m_chaps}</b>\n\n"
                    f"🔗 <i>Tap below to start reading right now:</i>",
                    reply_markup=buttons,
                    parse_mode="HTML"
                )
                return

    # 3. 🚫 Check for DUPLICATE Pending Requests
    existing = request_col.find_one({
        "manga_name": {"$regex": f"^{re.escape(query)}$", "$options": "i"},
        "status": "pending"
    })
    if existing:
        update.message.reply_text(
            f"📌 <b>Already in Queue!</b>\n\n"
            f"📚 <b>{html.escape(query)}</b> has already been requested and is pending admin review! 🕒",
            parse_mode="HTML"
        )
        return

    # 4. 📝 Insert new request into Database
    now_utc = datetime.now(timezone.utc)
    res = request_col.insert_one({
        "user_id": user.id,
        "username": user.full_name,
        "user_handle": f"@{user.username}" if user.username else "No handle",
        "manga_name": query,
        "status": "pending",
        "timestamp": now_utc,
        "admin_messages": {}
    })
    req_id = str(res.inserted_id)

    # 5. 📬 Notify User
    update.message.reply_text(
        f"✅ <b>Request Submitted!</b>\n\n"
        f"📚 <b>{html.escape(query)}</b> has been sent to our admin team! You will receive a direct DM as soon as it is reviewed or uploaded. 💕",
        parse_mode="HTML"
    )

    # 6. 🚨 Send Instant DM Alert to Admins & Owner
    admin_text = (
        f"📨 <b>New Manga Request Received!</b> 🌌\n\n"
        f"📚 <b>Manga:</b> <code>{html.escape(query)}</code>\n"
        f"👤 <b>User:</b> <a href='tg://user?id={user.id}'>{html.escape(user.full_name)}</a> ({f'@{user.username}' if user.username else f'ID: {user.id}'})\n"
        f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
        f"📅 <b>Date:</b> {now_utc.strftime('%Y-%m-%d %H:%M UTC')}"
    )

    admin_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Accept", callback_data=f"req_acc|{req_id}|{user.id}"),
            InlineKeyboardButton("❌ Decline", callback_data=f"req_dec|{req_id}|{user.id}")
        ],
        [
            InlineKeyboardButton("💬 Send Message to User", callback_data=f"req_msg|{req_id}|{user.id}")
        ]
    ])

    admin_ids = set([BOT_OWNER_ID] + get_all_sudo())
    admin_msg_ids = {}
    for aid in admin_ids:
        try:
            sent_msg = context.bot.send_message(
                chat_id=aid,
                text=admin_text,
                parse_mode="HTML",
                reply_markup=admin_keyboard
            )
            admin_msg_ids[str(aid)] = sent_msg.message_id
        except Exception:
            pass

    request_col.update_one({"_id": res.inserted_id}, {"$set": {"admin_messages": admin_msg_ids}})
    log_to_channel(context, admin_text)


# =========================================================
# 📋 /requestlist — View and manage pending requests (Admins)
# =========================================================
def request_list(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return update.message.reply_text("⛔ Only admins can view the request list.")

    requests = list(request_col.find({"status": "pending"}).sort("timestamp", -1).limit(10))
    if not requests:
        return update.message.reply_text("📭 No pending manga requests found.")

    update.message.reply_text(f"📋 <b>Pending Manga Requests ({len(requests)}):</b>", parse_mode="HTML")

    for req in requests:
        req_id = str(req.get("_id"))
        target_uid = str(req.get("user_id"))
        m_name = req.get("manga_name", "Unknown")
        u_name = req.get("username", "Unknown")
        u_handle = req.get("user_handle", "")

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Accept", callback_data=f"req_acc|{req_id}|{target_uid}"),
                InlineKeyboardButton("❌ Decline", callback_data=f"req_dec|{req_id}|{target_uid}")
            ],
            [
                InlineKeyboardButton("💬 Message User", callback_data=f"req_msg|{req_id}|{target_uid}")
            ]
        ])

        update.message.reply_text(
            f"📚 <b>{html.escape(m_name)}</b>\n"
            f"👤 Requested by: <b>{html.escape(u_name)}</b> ({u_handle})\n"
            f"🆔 User ID: <code>{target_uid}</code>",
            parse_mode="HTML",
            reply_markup=keyboard
        )


# =========================================================
# 🔘 Interactive Callback Handlers: Accept / Decline / Message
# =========================================================
def handle_request_callbacks(update: Update, context: CallbackContext):
    query = update.callback_query
    try:
        query.answer()
    except Exception:
        pass

    admin_user = query.from_user
    if not is_admin(admin_user.id):
        return query.edit_message_text("⛔ You are not allowed to perform this action.")

    data = query.data or ""
    parts = data.split("|")
    action = parts[0]

    # --- 1. ACCEPT FLOW ---
    if action == "req_acc":
        if len(parts) < 3: return
        req_id_str, user_id_str = parts[1], parts[2]
        req_id = ObjectId(req_id_str)
        target_user_id = int(user_id_str)

        req_doc = request_col.find_one({"_id": req_id})
        if not req_doc:
            return query.edit_message_text("⚠️ Request not found or already processed.")

        manga_name = req_doc.get("manga_name", "Manga")

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✨ Quick Accept DM", callback_data=f"req_sendacc|{req_id_str}|{target_user_id}"),
                InlineKeyboardButton("✍️ Custom Note", callback_data=f"req_customacc|{req_id_str}|{target_user_id}")
            ]
        ])

        query.edit_message_text(
            f"✅ <b>Accepting Request:</b> <code>{html.escape(manga_name)}</code>\n\n"
            f"Choose whether to send an instant acceptance notification or attach a custom message/link for the user:",
            parse_mode="HTML",
            reply_markup=keyboard
        )

    # --- 2. INSTANT ACCEPT EXECUTION ---
    elif action == "req_sendacc":
        if len(parts) < 3: return
        req_id_str, user_id_str = parts[1], parts[2]
        req_id = ObjectId(req_id_str)
        target_user_id = int(user_id_str)

        req_doc = request_col.find_one({"_id": req_id})
        manga_name = req_doc.get("manga_name", "Manga") if req_doc else "Manga"

        request_col.update_one({"_id": req_id}, {"$set": {"status": "completed", "completed_by": admin_user.id, "completed_by_name": admin_user.first_name}})
        _sync_admin_messages(context, req_doc, admin_user, "✅ <b>Accepted</b>")

        try:
            context.bot.send_message(
                chat_id=target_user_id,
                text=(
                    f"🎉 <b>Your Manga Request Was Accepted!</b> 🌌\n\n"
                    f"📚 <b>{html.escape(manga_name)}</b> has been approved by our admin team!\n\n"
                    f"<i>We are uploading the chapters now. Keep an eye on our channels! 💕</i>"
                ),
                parse_mode="HTML"
            )
            query.edit_message_text(f"✅ <b>Accepted!</b> User notified via DM about <b>{html.escape(manga_name)}</b>.", parse_mode="HTML")
        except Exception as e:
            query.edit_message_text(f"✅ Marked accepted, but could not DM user (Blocked/Privacy): {e}")

    # --- 3. DECLINE MENU ---
    elif action == "req_dec":
        if len(parts) < 3: return
        req_id_str, user_id_str = parts[1], parts[2]
        req_id = ObjectId(req_id_str)
        target_user_id = int(user_id_str)

        req_doc = request_col.find_one({"_id": req_id})
        manga_name = req_doc.get("manga_name", "Manga") if req_doc else "Manga"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📚 Already in Catalog", callback_data=f"req_senddec|{req_id_str}|{target_user_id}|already")],
            [InlineKeyboardButton("🚫 Not a Manga/Manhwa", callback_data=f"req_senddec|{req_id_str}|{target_user_id}|notmanga")],
            [InlineKeyboardButton("🔒 Licensed / Unavailable", callback_data=f"req_senddec|{req_id_str}|{target_user_id}|licensed")],
            [InlineKeyboardButton("✍️ Custom Reason...", callback_data=f"req_customdec|{req_id_str}|{target_user_id}")]
        ])

        query.edit_message_text(
            f"❌ <b>Decline Request:</b> <code>{html.escape(manga_name)}</code>\n\nSelect the reason to send to the user:",
            parse_mode="HTML",
            reply_markup=keyboard
        )

    # --- 4. PRESET DECLINE EXECUTION ---
    elif action == "req_senddec":
        if len(parts) < 4: return
        req_id_str, user_id_str, reason_code = parts[1], parts[2], parts[3]
        req_id = ObjectId(req_id_str)
        target_user_id = int(user_id_str)

        reasons = {
            "already": "This title is already available in our channels/web app. Please search using /manga or browse the Web Mini App.",
            "notmanga": "The requested title is not a valid manga, manhwa, or webtoon.",
            "licensed": "This title is currently licensed/DMCA restricted and cannot be uploaded at this time."
        }
        reason_text = reasons.get(reason_code, "Could not be fulfilled at this time.")

        req_doc = request_col.find_one({"_id": req_id})
        manga_name = req_doc.get("manga_name", "Manga") if req_doc else "Manga"

        request_col.update_one({"_id": req_id}, {"$set": {"status": "denied", "denied_by": admin_user.id, "denied_by_name": admin_user.first_name, "reason": reason_text}})
        _sync_admin_messages(context, req_doc, admin_user, "❌ <b>Declined</b>")

        try:
            context.bot.send_message(
                chat_id=target_user_id,
                text=(
                    f"❌ <b>Your Manga Request was Declined</b>\n\n"
                    f"📚 <b>Manga:</b> {html.escape(manga_name)}\n"
                    f"💬 <b>Reason:</b> {html.escape(reason_text)}\n\n"
                    f"<i>Feel free to request another title anytime! 💕</i>"
                ),
                parse_mode="HTML"
            )
            query.edit_message_text(f"❌ <b>Declined!</b> User notified with reason:\n<i>{reason_text}</i>", parse_mode="HTML")
        except Exception as e:
            query.edit_message_text(f"❌ Marked declined (could not DM user: {e})")

    # --- 5. CUSTOM MESSAGE PROMPTS ---
    elif action in ["req_msg", "req_customacc", "req_customdec"]:
        if len(parts) < 3: return
        req_id_str, user_id_str = parts[1], parts[2]
        target_user_id = int(user_id_str)

        waiting_admin_reply[admin_user.id] = {
            "req_id": req_id_str,
            "target_user_id": target_user_id,
            "action": action
        }

        query.edit_message_text(
            f"✍️ <b>Send Direct Message to User:</b>\n\n"
            f"Now simply send your reply message in this chat, and the bot will immediately forward it to the user as a DM!\n\n"
            f"<i>Type /cancel to abort.</i>",
            parse_mode="HTML"
        )


# =========================================================
# 💬 Admin Custom Reply Message Receiver
# =========================================================
def handle_admin_reply_text(update: Update, context: CallbackContext) -> bool:
    """Captures admin's text when in waiting_admin_reply state and sends as DM."""
    if not update.message or not update.message.text:
        return False

    admin_user = update.effective_user
    if admin_user.id not in waiting_admin_reply:
        return False

    state = waiting_admin_reply.pop(admin_user.id)
    text = update.message.text.strip()

    if text.lower() == "/cancel":
        update.message.reply_text("❌ Action cancelled.")
        return True

    target_uid = state["target_user_id"]
    req_id_str = state["req_id"]
    action = state["action"]

    req_doc = request_col.find_one({"_id": ObjectId(req_id_str)}) if req_id_str else None
    m_name = req_doc.get("manga_name", "Manga") if req_doc else "Manga"

    try:
        if action == "req_customacc":
            request_col.update_one({"_id": ObjectId(req_id_str)}, {"$set": {"status": "completed", "completed_by": admin_user.id, "completed_by_name": admin_user.first_name, "admin_note": text}})
            _sync_admin_messages(context, req_doc, admin_user, "✅ <b>Accepted (Custom Note)</b>")
            dm_text = (
                f"🎉 <b>Your Manga Request Was Accepted!</b> 🌌\n\n"
                f"📚 <b>{html.escape(m_name)}</b>\n"
                f"💬 <b>Admin Note:</b> {html.escape(text)}\n\n"
                f"<i>Happy reading! 💕</i>"
            )
        elif action == "req_customdec":
            request_col.update_one({"_id": ObjectId(req_id_str)}, {"$set": {"status": "denied", "denied_by": admin_user.id, "denied_by_name": admin_user.first_name, "reason": text}})
            _sync_admin_messages(context, req_doc, admin_user, "❌ <b>Declined</b>")
            dm_text = (
                f"❌ <b>Your Manga Request was Declined</b>\n\n"
                f"📚 <b>{html.escape(m_name)}</b>\n"
                f"💬 <b>Reason:</b> {html.escape(text)}\n\n"
                f"<i>Feel free to request another title anytime! 💕</i>"
            )
        else:  # Direct message
            dm_text = (
                f"💬 <b>Message from Bot Admin regarding '{html.escape(m_name)}':</b>\n\n"
                f"{html.escape(text)}"
            )

        context.bot.send_message(chat_id=target_uid, text=dm_text, parse_mode="HTML")
        update.message.reply_text(f"✅ <b>Message Sent!</b> Delivered to user <code>{target_uid}</code> successfully!", parse_mode="HTML")
    except Exception as e:
        update.message.reply_text(f"❌ Failed to deliver DM to user {target_uid}: {e}")

    return True


# =========================================================
# 💬 /replyreq <user_id> <message> (Command alternative)
# =========================================================
def replyreq_cmd(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        return update.message.reply_text("🚫 Sudo only.")

    if len(context.args) < 2:
        return update.message.reply_text("📌 Usage: <code>/replyreq <user_id> <your message></code>", parse_mode="HTML")

    try:
        target_uid = int(context.args[0])
        msg_text = " ".join(context.args[1:]).strip()

        context.bot.send_message(
            chat_id=target_uid,
            text=f"💬 <b>Message from Galactic Bot Admin:</b>\n\n{html.escape(msg_text)}",
            parse_mode="HTML"
        )
        update.message.reply_text(f"✅ Message sent to <code>{target_uid}</code>!", parse_mode="HTML")
    except Exception as e:
        update.message.reply_text(f"❌ Failed to send message: {e}")

