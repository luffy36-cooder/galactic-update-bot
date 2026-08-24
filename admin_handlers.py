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
    if not is_admin(update.effective_user.id):
        return update.message.reply_text("🚫 Sudo only.")

    from database import auto_sync_all_chapters, manga_col
    msg = update.message.reply_text("🔄 Auto-scanning all manga chapters from database...")

    updated = auto_sync_all_chapters()
    total_with_chaps = sum(1 for m in manga_col.find() if m.get("total_chapters", 0) > 0)
    total_manga = manga_col.count_documents({})

    msg.edit_text(
        f"✅ <b>Chapter Auto-Sync Complete!</b>\n\n"
        f"• Newly updated: <b>{updated}</b>\n"
        f"• Manga with indexed chapters: <b>{total_with_chaps}/{total_manga}</b>\n\n"
        f"<i>All manga in Web App & bot now have updated chapter counts.</i>",
        parse_mode="HTML"
    )
