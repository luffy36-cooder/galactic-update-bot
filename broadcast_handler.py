import re
import time
import html
import logging
import threading
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext
from database import (
    get_all_channels,
    get_manga_by_id,
    search_manga_by_name,
    broadcast_log_col,
    modes_col,
    is_sudo,
    db
)
from config import BOT_OWNER_ID

logger = logging.getLogger(__name__)


# -------------------------
# Permission check
# -------------------------
def is_admin(user_id: int) -> bool:
    return user_id == BOT_OWNER_ID or is_sudo(user_id)


# -------------------------
# Helper: Parse Inline Buttons
# -------------------------
def parse_inline_buttons(text: str):
    """
    Parses 'button=Text | URL' or 'buttons=T1|U1, T2|U2' from text.
    Returns (cleaned_text, InlineKeyboardMarkup or None)
    """
    if not text:
        return text, None

    buttons_list = []
    cleaned_text = text

    # Check for 'buttons=' (multi-button)
    multi_match = re.search(r'buttons?\s*=\s*(.+)$', text, re.IGNORECASE | re.DOTALL)
    if multi_match:
        btn_raw = multi_match.group(1).strip()
        cleaned_text = text[:multi_match.start()].strip()
        row = []
        for pair in btn_raw.split(","):
            if "|" in pair:
                parts = pair.split("|", 1)
                b_text = parts[0].strip()
                b_url = parts[1].strip()
                if b_text and b_url.startswith("http"):
                    row.append(InlineKeyboardButton(b_text, url=b_url))
        if row:
            buttons_list.append(row)

    # Check for 'button=' (single button)
    elif "button=" in text.lower():
        parts = text.split("button=", 1)
        cleaned_text = parts[0].strip()
        btn_part = parts[1].strip()
        if "|" in btn_part:
            b_text, b_url = btn_part.split("|", 1)
            b_text, b_url = b_text.strip(), b_url.strip()
            if b_text and b_url.startswith("http"):
                buttons_list.append([InlineKeyboardButton(b_text, url=b_url)])

    markup = InlineKeyboardMarkup(buttons_list) if buttons_list else None
    return cleaned_text, markup


# -------------------------
# 📢 /broadcast Command (Multi-Targeted & Multi-Media)
# -------------------------
def broadcast_cmd(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = user.id

    if not is_admin(user_id):
        return update.message.reply_text("❌ You are not allowed to use this command.")

    args = list(context.args) if context.args else []
    reply = update.message.reply_to_message

    if not args and not reply:
        return update.message.reply_text(
            "📢 <b>Broadcast Command Guide</b> 🌌\n\n"
            "• <b>All Channels:</b>\n"
            "  <code>/broadcast &lt;message&gt;</code>\n"
            "  <i>(Or reply to any text, photo, video, PDF, or sticker with /broadcast)</i>\n\n"
            "• <b>Specific Channel(s) by ID:</b>\n"
            "  <code>/broadcast -1002638509926 &lt;message&gt;</code>\n"
            "  <code>/broadcast -100123,-100456 &lt;message&gt;</code>\n\n"
            "• <b>Specific Manga Channel by Name:</b>\n"
            "  <code>/broadcast manga=Solo Leveling &lt;message&gt;</code>\n\n"
            "• <b>All Group Chats (GC):</b>\n"
            "  <code>/broadcast gc &lt;message&gt;</code>\n\n"
            "• <b>Auto-Pin Option (📌 Pin Message):</b>\n"
            "  <code>/broadcast -pin &lt;message&gt;</code>\n"
            "  <code>/broadcast -pin gc &lt;message&gt;</code>\n"
            "  <i>(Or reply with <code>/broadcast -pin</code>)</i>\n\n"
            "• <b>Add Custom Buttons:</b>\n"
            "  <code>/broadcast Hello! button=Open Web|https://t.me/bot?start=web</code>\n\n"
            "• <b>Check History:</b> <code>/bdst</code>\n"
            "• <b>Undo / Delete:</b> <code>/delete_broadcast &lt;id&gt;</code>",
            parse_mode="HTML"
        )

    # 1. Determine Pinning Option
    should_pin = False
    filtered_args = []
    for a in args:
        if a.lower() in ["-pin", "pin", "--pin"]:
            should_pin = True
        else:
            filtered_args.append(a)
    args = filtered_args

    # 2. Determine Target Type & Target List
    target_type = "all_channels"
    target_desc = "All Manga Channels"
    target_chat_ids = []

    # Check if first arg specifies target
    if args:
        first_arg = args[0].lower()
        if first_arg in ["gc", "groups", "group"]:
            target_type = "groups"
            target_desc = "All Group Chats"
            args = args[1:]
            target_chat_ids = list(modes_col.distinct("chat_id"))
        elif first_arg.startswith("manga=") or first_arg.startswith("channel=") or first_arg.startswith("title="):
            target_type = "specific_manga"
            m_query = args[0].split("=", 1)[1].strip()
            args = args[1:]
            m_res = search_manga_by_name(m_query, limit=1)
            if m_res and m_res[0].get("channel_id"):
                cid = m_res[0]["channel_id"]
                target_chat_ids = [cid]
                target_desc = f"{m_res[0].get('name', 'Manga')} ({cid})"
            else:
                return update.message.reply_text(f"❌ Manga channel not found for query: <code>{html.escape(m_query)}</code>", parse_mode="HTML")
        elif first_arg.startswith("-100") or ("," in first_arg and "-100" in first_arg):
            target_type = "specific_ids"
            args = args[1:]
            for raw_id in first_arg.split(","):
                try:
                    target_chat_ids.append(int(raw_id.strip()))
                except ValueError:
                    pass
            target_desc = f"{len(target_chat_ids)} Selected Channel(s)"
        elif first_arg in ["all", "channels"]:
            args = args[1:]
            target_type = "all_channels"
            target_chat_ids = get_all_channels()

    if not target_chat_ids:
        if target_type == "all_channels":
            target_chat_ids = get_all_channels()
            target_desc = f"All Manga Channels ({len(target_chat_ids)})"

    if not target_chat_ids:
        return update.message.reply_text("⚠️ No target channels or groups found in database.")

    raw_text = " ".join(args).strip() if args else None
    cleaned_text, custom_buttons = parse_inline_buttons(raw_text)

    if not reply and not cleaned_text:
        return update.message.reply_text("❌ Nothing to broadcast. Provide text or reply to a media message.")

    broadcast_id = update.message.message_id
    total_targets = len(target_chat_ids)
    pin_str = " (📌 Auto-Pin Enabled)" if should_pin else ""

    status_msg = update.message.reply_text(
        f"🚀 <b>Starting Broadcast #{broadcast_id}...</b>\n\n"
        f"🎯 <b>Target:</b> <code>{html.escape(target_desc)}</code>{pin_str}\n"
        f"📊 <b>Total Chats:</b> <b>{total_targets}</b>\n\n"
        f"<i>Sending in background...</i>",
        parse_mode="HTML"
    )

    def run_broadcast():
        sent_records = []
        sent_count = 0
        failed_count = 0
        preview = cleaned_text or (reply.caption if reply else None) or "[Media Attachment]"

        for cid in target_chat_ids:
            try:
                time.sleep(0.04)  # Safe flood pacing
                if reply:
                    sent = context.bot.copy_message(
                        chat_id=cid,
                        from_chat_id=reply.chat_id,
                        message_id=reply.message_id,
                        reply_markup=custom_buttons
                    )
                    msg_id = sent.message_id
                else:
                    sent = context.bot.send_message(
                        chat_id=cid,
                        text=cleaned_text,
                        parse_mode="HTML",
                        reply_markup=custom_buttons,
                        disable_web_page_preview=False
                    )
                    msg_id = sent.message_id

                # Auto-Pin message if requested
                if should_pin:
                    try:
                        context.bot.pin_chat_message(chat_id=cid, message_id=msg_id, disable_notification=False)
                    except Exception as pe:
                        logger.debug(f"Pin notice in {cid}: {pe}")

                sent_records.append({"chat_id": cid, "msg_id": msg_id})
                sent_count += 1
            except Exception as e:
                failed_count += 1
                logger.warning(f"❌ Broadcast fail in {cid}: {e}")

        # Store complete record in MongoDB for /bdst and /delete_broadcast
        broadcast_log_col.insert_one({
            "broadcast_id": broadcast_id,
            "created_at": time.time(),
            "admin_id": user_id,
            "target_type": target_type,
            "target_desc": target_desc,
            "is_pinned": should_pin,
            "content_preview": (preview[:80] + "...") if len(preview) > 80 else preview,
            "total_targets": total_targets,
            "sent_count": sent_count,
            "failed_count": failed_count,
            "channel_msgs": sent_records
        })

        pinned_badge = " • 📌 Pinned" if should_pin else ""
        try:
            status_msg.edit_text(
                f"✅ <b>Broadcast #{broadcast_id} Complete!</b> 🌌\n\n"
                f"🎯 <b>Target:</b> {html.escape(target_desc)}{pinned_badge}\n"
                f"📤 <b>Successfully Sent:</b> <b>{sent_count}</b>\n"
                f"❌ <b>Failed / Inaccessible:</b> <b>{failed_count}</b>\n"
                f"🆔 <b>Broadcast ID:</b> <code>{broadcast_id}</code>\n\n"
                f"<i>To undo / delete this broadcast:</i>\n"
                f"<code>/delete_broadcast {broadcast_id}</code>",
                parse_mode="HTML"
            )
        except Exception:
            context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"✅ <b>Broadcast #{broadcast_id} Finished!</b>\n"
                    f"Sent: {sent_count} | Failed: {failed_count}{pinned_badge}\n"
                    f"To undo: <code>/delete_broadcast {broadcast_id}</code>"
                ),
                parse_mode="HTML"
            )

    threading.Thread(target=run_broadcast, daemon=True, name="BroadcastWorker").start()


# -------------------------
# 📊 /bdst Command (Broadcast Status & History Inspector)
# -------------------------
def bdst_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return update.message.reply_text("❌ You are not authorized to view broadcast status.")

    args = context.args
    dmbroadcast_log_col = db["dmbroadcast_log"]

    # Detailed single broadcast inspect
    if args and args[0].isdigit():
        bid = int(args[0])
        doc = broadcast_log_col.find_one({"broadcast_id": bid})
        is_dm = False
        if not doc:
            doc = dmbroadcast_log_col.find_one({"broadcast_id": bid})
            is_dm = True

        if not doc:
            return update.message.reply_text(f"⚠️ No broadcast record found for ID: <code>{bid}</code>", parse_mode="HTML")

        dt = datetime.fromtimestamp(doc.get("created_at", time.time()), timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        msgs = doc.get("channel_msgs") or doc.get("records") or []
        del_cmd = f"/delete_dmbroadcast {bid}" if is_dm else f"/delete_broadcast {bid}"

        return update.message.reply_text(
            f"📊 <b>Broadcast Report #{bid}</b> 🌌\n\n"
            f"🎯 <b>Target:</b> {html.escape(doc.get('target_desc', 'Unknown'))}\n"
            f"📅 <b>Date:</b> {dt}\n"
            f"👤 <b>Admin ID:</b> <code>{doc.get('admin_id', 'N/A')}</code>\n"
            f"📝 <b>Preview:</b> <i>{html.escape(doc.get('content_preview', 'N/A'))}</i>\n\n"
            f"📈 <b>Stats:</b>\n"
            f"• Total Targeted: <b>{doc.get('total_targets', len(msgs))}</b>\n"
            f"• Delivered: <b>{doc.get('sent_count', len(msgs))}</b>\n"
            f"• Failed: <b>{doc.get('failed_count', 0)}</b>\n\n"
            f"🗑️ <b>Delete Action:</b>\n<code>{del_cmd}</code>",
            parse_mode="HTML"
        )

    # List recent broadcasts (Merge Channel + DM broadcasts)
    ch_logs = list(broadcast_log_col.find().sort("created_at", -1).limit(8))
    dm_logs = list(dmbroadcast_log_col.find().sort("created_at", -1).limit(8))

    for item in ch_logs: item["_is_dm"] = False
    for item in dm_logs: item["_is_dm"] = True

    combined = ch_logs + dm_logs
    combined.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    recent_logs = combined[:8]

    if not recent_logs:
        return update.message.reply_text("📭 <b>No recent broadcasts recorded in database.</b>", parse_mode="HTML")

    text = "📡 <b>Recent Broadcasts History</b> 🌌\n\n"
    for item in recent_logs:
        bid = item.get("broadcast_id")
        target = item.get("target_desc", "Channels")
        sent = item.get("sent_count", len(item.get("channel_msgs", []) or item.get("records", [])))
        failed = item.get("failed_count", 0)
        dt = datetime.fromtimestamp(item.get("created_at", time.time()), timezone.utc).strftime("%d %b %H:%M")
        del_cmd = f"/delete_dmbroadcast {bid}" if item.get("_is_dm") else f"/delete_broadcast {bid}"

        text += (
            f"🆔 <b>ID:</b> <code>{bid}</code> | 🕒 <i>{dt}</i>\n"
            f"🎯 <b>Type:</b> <code>{html.escape(target)}</code>\n"
            f"📊 <b>Delivery:</b> ✅ {sent} sent • ❌ {failed} failed\n"
            f"🗑️ <code>{del_cmd}</code>\n"
            f"──────────────────\n"
        )

    text += "\n<i>Tip: Type <code>/bdst &lt;id&gt;</code> for detailed report.</i>"
    update.message.reply_text(text, parse_mode="HTML")


# -------------------------
# 🗑️ /delete_broadcast Command (Safe Multi-Channel Eraser)
# -------------------------
def delete_broadcast_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return update.message.reply_text("❌ You are not allowed to use this command.")

    broadcast_id = None
    reply = update.message.reply_to_message

    if reply:
        # Check if replying directly to a broadcast source message
        broadcast_id = reply.message_id
    elif context.args and context.args[0].isdigit():
        broadcast_id = int(context.args[0])

    if not broadcast_id:
        # Fallback: check most recent broadcast
        latest = broadcast_log_col.find().sort("created_at", -1).limit(1)
        latest_doc = next(latest, None)
        if latest_doc:
            broadcast_id = latest_doc.get("broadcast_id")

    if not broadcast_id:
        return update.message.reply_text(
            "❗ <b>Usage:</b>\n"
            "• <code>/delete_broadcast &lt;broadcast_id&gt;</code>\n"
            "• Or reply to the broadcast message with <code>/delete_broadcast</code>\n\n"
            "<i>Type <code>/bdst</code> to find your Broadcast ID.</i>",
            parse_mode="HTML"
        )

    log_entry = broadcast_log_col.find_one({"broadcast_id": broadcast_id})
    if not log_entry or not log_entry.get("channel_msgs"):
        return update.message.reply_text(f"⚠️ No active broadcast records found for ID <code>{broadcast_id}</code>.", parse_mode="HTML")

    status_msg = update.message.reply_text(f"🗑️ Deleting broadcast #{broadcast_id} across all chats...")

    def run_deletion():
        deleted_count = 0
        failed_count = 0
        channel_msgs = log_entry.get("channel_msgs", [])

        for item in channel_msgs:
            try:
                time.sleep(0.04)
                context.bot.delete_message(chat_id=item["chat_id"], message_id=item["msg_id"])
                deleted_count += 1
            except Exception:
                failed_count += 1

        broadcast_log_col.delete_one({"_id": log_entry["_id"]})

        try:
            status_msg.edit_text(
                f"✅ <b>Broadcast #{broadcast_id} Deleted!</b>\n\n"
                f"🗑️ <b>Messages Removed:</b> <b>{deleted_count}</b>\n"
                f"⚠️ <b>Inaccessible / Expired:</b> <b>{failed_count}</b>",
                parse_mode="HTML"
            )
        except Exception:
            context.bot.send_message(
                chat_id=user_id,
                text=f"✅ Broadcast #{broadcast_id} deleted in {deleted_count} chats.",
                parse_mode="HTML"
            )

    threading.Thread(target=run_deletion, daemon=True, name="BroadcastDeleteWorker").start()

