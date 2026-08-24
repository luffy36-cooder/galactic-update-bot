import html
import logging
from telegram import Update
from telegram.ext import CallbackContext
from database import (
    list_all_manga,
    remove_manga_by_name,
    edit_manga_link_or_name,
    search_manga_by_name,
    manga_col,
    is_sudo,
    add_sudo,
    remove_sudo,
    get_all_sudo
)
from config import BOT_OWNER_ID

logger = logging.getLogger(__name__)


# 🔐 Unified admin check
def is_admin(user_id: int) -> bool:
    return user_id == BOT_OWNER_ID or is_sudo(user_id)


# ❌ /removemanga <name>
def removemanga_cmd(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        return update.message.reply_text("❌ You're not allowed to use this command.")

    if not context.args:
        return update.message.reply_text("Usage: /removemanga <name>")

    name = " ".join(context.args).strip()
    success = remove_manga_by_name(name)
    if success:
        update.message.reply_text(f"✅ Removed manga: <b>{html.escape(name)}</b>", parse_mode="HTML")
    else:
        update.message.reply_text(f"⚠️ Manga not found: <b>{html.escape(name)}</b>", parse_mode="HTML")


# ✏️ /editmanga <old_name> | <new_name> | <new_link>
def editmanga_cmd(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        return update.message.reply_text("❌ You're not allowed to use this command.")

    full_text = " ".join(context.args).strip()
    if "|" in full_text:
        parts = [p.strip() for p in full_text.split("|")]
        if len(parts) < 3:
            return update.message.reply_text("Usage:\n/editmanga <old_name> | <new_name> | <new_link>")
        old_name, new_name, new_link = parts[0], parts[1], parts[2]
    else:
        if len(context.args) < 3:
            return update.message.reply_text("Usage:\n/editmanga <old_name> | <new_name> | <new_link>")
        old_name, new_name, new_link = context.args[0], context.args[1], context.args[2]

    updated = edit_manga_link_or_name(old_name, new_name, new_link)
    if updated and updated.modified_count > 0:
        update.message.reply_text(
            f"✅ Updated manga:\n• <b>{html.escape(old_name)}</b> ➔ <b>{html.escape(new_name)}</b>\n🔗 {html.escape(new_link)}",
            parse_mode="HTML"
        )
    else:
        update.message.reply_text(
            f"⚠️ Could not find or update manga: <b>{html.escape(old_name)}</b>",
            parse_mode="HTML"
        )


# 🔢 /setchapters <manga name> <total_chapters>
def set_chapters_cmd(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        return update.message.reply_text("❌ You're not allowed to use this command.")

    if len(context.args) < 2:
        return update.message.reply_text("❗ Usage: /setchapters <manga name> <total_chapters>")

    try:
        total = int(context.args[-1])
        manga_name = " ".join(context.args[:-1]).strip()
    except ValueError:
        return update.message.reply_text("❗ Invalid chapter count. Must be a positive number.")

    if total <= 0:
        return update.message.reply_text("❗ Total chapters must be greater than 0.")

    manga_list = search_manga_by_name(manga_name)
    if not manga_list:
        return update.message.reply_text("❌ Manga not found.")

    manga = manga_list[0]
    result = manga_col.update_one(
        {"channel_id": manga["channel_id"]},
        {"$set": {"total_chapters": total}}
    )

    if result.acknowledged:
        update.message.reply_text(
            f"✅ Updated <b>{html.escape(manga.get('name', manga_name))}</b> total chapters ➔ <b>{total}</b>.",
            parse_mode="HTML"
        )
    else:
        update.message.reply_text("⚠️ Could not update.")


# ➕ /addadmins <user_id> (Owner or Admin)
def addadmins_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return update.message.reply_text("🚫 You're not allowed to do this.")

    if not context.args or not context.args[0].isdigit():
        return update.message.reply_text("❗ Usage: /addadmins <user_id>")

    target_id = int(context.args[0])
    if is_sudo(target_id):
        return update.message.reply_text("⚠️ This user is already an admin.")

    add_sudo(target_id)
    update.message.reply_text(
        f"✅ User <code>{target_id}</code> added to admin/sudo list.",
        parse_mode="HTML"
    )


# ➖ /removeadmins <user_id> (Owner only)
def removeadmins_cmd(update: Update, context: CallbackContext):
    if update.effective_user.id != BOT_OWNER_ID:
        return update.message.reply_text("🚫 Only the bot owner can remove admins.")

    if not context.args or not context.args[0].isdigit():
        return update.message.reply_text("❗ Usage: /removeadmins <user_id>")

    target_id = int(context.args[0])
    if target_id == BOT_OWNER_ID:
        return update.message.reply_text("🚫 You cannot remove the bot owner.")

    if not is_sudo(target_id):
        return update.message.reply_text("⚠️ This user is not in the admin list.")

    remove_sudo(target_id)
    update.message.reply_text(
        f"❌ User <code>{target_id}</code> removed from admin/sudo list.",
        parse_mode="HTML"
    )


# 📋 /sudo — Show all sudo users
def sudo_cmd(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        return update.message.reply_text("🚫 You're not allowed to view sudo list.")

    sudo_users = get_all_sudo()
    if BOT_OWNER_ID not in sudo_users:
        sudo_users.insert(0, BOT_OWNER_ID)

    sudo_lines = []
    for uid in sudo_users:
        tag = "👑 Owner" if uid == BOT_OWNER_ID else "🛡️ Admin"
        sudo_lines.append(f"• <a href='tg://user?id={uid}'>{uid}</a> ({tag})")

    sudo_list_text = "\n".join(sudo_lines)
    update.message.reply_text(
        f"🛡️ <b>Current Admins & Sudo Users:</b>\n\n{sudo_list_text}",
        parse_mode="HTML",
        disable_web_page_preview=True
    )


# 🔄 /syncchapters or /autochapters — Automatically scan and update chapter counts for all manga
def syncchapters_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return update.message.reply_text("🚫 Sudo only.")

    from database import manga_col, posted_chapter_col, chapter_files_col, bookmarks_col, _invalidate_manga_cache
    import threading
    import time
    import html

    status_msg = update.message.reply_text(
        "🔄 <b>Starting Chapter Auto-Sync...</b>\n\n"
        "<code>[░░░░░░░░░░░░] 0%</code>\n"
        "<i>Scanning database records...</i>",
        parse_mode="HTML"
    )

    def run_sync():
        all_manga = list(manga_col.find())
        total_manga = len(all_manga)
        updated_count = 0
        scanned_count = 0
        last_edit_time = time.time()

        for m in all_manga:
            cid = m.get("channel_id")
            m_name = m.get("name", "Unknown")
            scanned_count += 1

            if not cid:
                continue

            highest_chap = m.get("total_chapters", 0) or 0

            # 1. Check posted_chapter_col
            posted_doc = posted_chapter_col.find_one({"channel_id": cid})
            if posted_doc and posted_doc.get("chapters"):
                for c in posted_doc["chapters"]:
                    try:
                        c_int = int(c)
                        if c_int > highest_chap:
                            highest_chap = c_int
                    except (ValueError, TypeError):
                        pass

            # 2. Check chapter_files_col
            ch_files = list(chapter_files_col.find({"channel_id": cid}))
            for cf in ch_files:
                c_int = cf.get("chapter")
                if c_int and isinstance(c_int, int) and c_int > highest_chap:
                    highest_chap = c_int

            # 3. Check bookmarks_col
            if m_name:
                bm_docs = list(bookmarks_col.find({"$or": [{"channel_id": cid}, {"manga": m_name}]}))
                for b in bm_docs:
                    try:
                        c_int = int(b.get("chapter", 0))
                        if c_int > highest_chap:
                            highest_chap = c_int
                    except (ValueError, TypeError):
                        pass

            if highest_chap > 0 and highest_chap != m.get("total_chapters"):
                manga_col.update_one({"channel_id": cid}, {"$set": {"total_chapters": highest_chap}})
                updated_count += 1

            now = time.time()
            if now - last_edit_time >= 2.5 or scanned_count == total_manga:
                last_edit_time = now
                percent = int((scanned_count / total_manga) * 100) if total_manga > 0 else 0
                filled = int((scanned_count / total_manga) * 12) if total_manga > 0 else 0
                bar = "█" * filled + "░" * (12 - filled)

                try:
                    status_msg.edit_text(
                        f"🔄 <b>Auto-Syncing Manga Chapters...</b>\n\n"
                        f"<code>[{bar}] {percent}%</code> ({scanned_count}/{total_manga} manga)\n\n"
                        f"📚 <b>Current:</b> <code>{html.escape(m_name[:35])}</code>\n"
                        f"📄 <b>Max Chapter:</b> <b>{highest_chap}</b>\n"
                        f"🔄 <b>Updated Titles:</b> <b>{updated_count}</b>\n\n"
                        f"<i>Matching posts, indexed files & bookmarks...</i>",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

        if updated_count > 0:
            _invalidate_manga_cache()

        total_with_chaps = sum(1 for x in manga_col.find() if x.get("total_chapters", 0) > 0)
        try:
            status_msg.edit_text(
                f"✅ <b>Chapter Auto-Sync Complete!</b>\n\n"
                f"<code>[████████████] 100%</code>\n\n"
                f"• <b>Newly Updated Titles:</b> {updated_count}\n"
                f"• <b>Manga with Indexed Chapters:</b> {total_with_chaps}/{total_manga}\n\n"
                f"<i>All manga in Web App & bot now have updated chapter counts! 🚀</i>",
                parse_mode="HTML"
            )
        except Exception:
            context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"✅ <b>Chapter Auto-Sync Complete!</b>\n\n"
                    f"• Newly updated: <b>{updated_count}</b>\n"
                    f"• Manga with indexed chapters: <b>{total_with_chaps}/{total_manga}</b>"
                ),
                parse_mode="HTML"
            )

    threading.Thread(target=run_sync, daemon=True, name="ChapterSyncWorker").start()


# 📥 Forward PDF Indexer — Bulk forward past chapter PDFs in bot PM to index them for Web Reader!
def handle_forwarded_chapter(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    message = update.message
    if not message or not message.document:
        return

    doc = message.document
    if not doc.file_name or not doc.file_name.lower().endswith(".pdf"):
        return

    import re
    from database import get_manga_by_id, save_chapter_file, get_all_manga_cached
    from channel_handler import extract_chapter_number

    channel_id = None
    if message.forward_from_chat:
        channel_id = message.forward_from_chat.id

    chapter = extract_chapter_number(doc.file_name)
    if chapter is None:
        return

    manga_title = "Unknown Manga"
    if channel_id:
        manga = get_manga_by_id(channel_id)
        if manga:
            manga_title = manga.get("name", "Manga")
    else:
        # Match manga title against registered manga database
        clean_name = re.sub(r'[\d._-]+', ' ', doc.file_name.rsplit('.', 1)[0]).strip().lower()
        for m in get_all_manga_cached():
            m_name = (m.get("name") or "").lower()
            if m_name and (m_name in clean_name or clean_name in m_name):
                channel_id = m.get("channel_id")
                manga_title = m.get("name")
                break

    if not channel_id:
        return update.message.reply_text(
            f"⚠️ Could not match <code>{doc.file_name}</code> to a registered manga. Please forward directly from the channel or rename with the manga name.",
            parse_mode="HTML"
        )

    save_chapter_file(channel_id, chapter, doc.file_id, doc.file_name, message.message_id)
    update.message.reply_text(
        f"⚡ <b>Indexed for In-App Webtoon Reader!</b>\n\n"
        f"📚 <b>{manga_title}</b> — Chapter <b>{chapter}</b>\n"
        f"📄 File: <code>{doc.file_name}</code>\n\n"
        f"<i>This chapter will now open and stream immediately inside the Web Mini App! 🚀</i>",
        parse_mode="HTML"
    )


# 🛰️ /scanallchannels — Auto-scan past messages across all channels to index past PDF files!
def scanallchannels_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return update.message.reply_text("🚫 Sudo only.")

    from database import manga_col
    from tg_streamer import get_streamer
    import threading
    import time
    import html

    status_msg = update.message.reply_text(
        "🛰️ <b>Starting High-Speed MTProto Channel Scan...</b>\n\n"
        "<code>[░░░░░░░░░░░░] 0%</code>\n"
        "<i>Connecting to Telegram MTProto servers...</i>",
        parse_mode="HTML"
    )

    def run_scan():
        streamer = get_streamer()
        mangas = list(manga_col.find({"channel_id": {"$ne": None}}))
        total_channels = len(mangas)
        total_found = 0
        channels_scanned = 0
        last_edit_time = time.time()

        for m in mangas:
            cid = m.get("channel_id")
            m_name = m.get("name", "Unknown")
            highest_ch = m.get("total_chapters", 0) or 0
            max_range = max(350, highest_ch + 60)

            try:
                found = streamer.scan_channel_batch(cid, start_id=1, end_id=max_range)
                total_found += found
            except Exception as e:
                logger.error(f"Error scanning channel {cid} ({m_name}): {e}")

            channels_scanned += 1
            now = time.time()

            # Update progress bar in Telegram every 3 seconds or on the last channel
            if now - last_edit_time >= 3.0 or channels_scanned == total_channels:
                last_edit_time = now
                percent = int((channels_scanned / total_channels) * 100) if total_channels > 0 else 0
                filled = int((channels_scanned / total_channels) * 12) if total_channels > 0 else 0
                bar = "█" * filled + "░" * (12 - filled)

                try:
                    status_msg.edit_text(
                        f"🛰️ <b>Scanning Manga Channels via MTProto...</b>\n\n"
                        f"<code>[{bar}] {percent}%</code> ({channels_scanned}/{total_channels} channels)\n\n"
                        f"📚 <b>Current:</b> <code>{html.escape(m_name[:35])}</code>\n"
                        f"📄 <b>PDF Chapters Found:</b> <b>{total_found}</b>\n\n"
                        f"<i>Running fast batch scanner in background...</i>",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

        # Final completion message
        try:
            status_msg.edit_text(
                f"🎉 <b>High-Speed MTProto Scan Complete!</b>\n\n"
                f"<code>[████████████] 100%</code>\n\n"
                f"• <b>Total Channels Scanned:</b> {channels_scanned}\n"
                f"• <b>Total PDF Chapters Indexed:</b> {total_found}\n\n"
                f"<i>All manga in the Web Mini App are now 100% indexed and streamable without size limits! 🚀</i>",
                parse_mode="HTML"
            )
        except Exception:
            context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"🎉 <b>High-Speed MTProto Scan Complete!</b>\n\n"
                    f"• Total Channels Scanned: <b>{channels_scanned}</b>\n"
                    f"• Total PDF Chapters Indexed: <b>{total_found}</b>\n\n"
                    f"<i>All manga in the Web Mini App are now 100% indexed and streamable! 🚀</i>"
                ),
                parse_mode="HTML"
            )

    threading.Thread(target=run_scan, daemon=True, name="MTProtoLiveScanner").start()
