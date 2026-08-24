import html
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext
from database import (
    save_user_bookmark,
    get_user_bookmarks,
    remove_bookmark,
    clear_user_bookmarks,
    search_manga_by_name,
    get_manga_by_id
)


# 📌 /bookmark <manga name> <chapter>
def bookmark_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    args = context.args

    if not args or len(args) < 2:
        update.message.reply_text("❗ Usage: /bookmark <manga name> <chapter>")
        return

    *name_parts, chapter_str = args
    manga_input = " ".join(name_parts).strip()

    if len(manga_input) < 1:
        update.message.reply_text("❌ Please enter a valid manga name.")
        return

    if not chapter_str.isdigit():
        update.message.reply_text("❌ Chapter must be a positive number.")
        return
    chapter = int(chapter_str)

    manga_list = search_manga_by_name(manga_input)
    if not manga_list:
        update.message.reply_text("❌ Manga not found. Please check the spelling or search with /manga.")
        return

    best_match = manga_list[0]
    manga_name = best_match.get("name", manga_input)
    total_chapters = best_match.get("total_chapters")

    if total_chapters and chapter > total_chapters:
        update.message.reply_text(
            f"❌ You cannot bookmark Chapter {chapter} because <b>{html.escape(manga_name)}</b> has only {total_chapters} chapters.",
            parse_mode="HTML"
        )
        return

    bookmarks = get_user_bookmarks(user_id)
    if len(bookmarks) >= 30:
        update.message.reply_text("🚫 You can only bookmark up to 30 manga. Clear some with /mybookmarks.")
        return

    success = save_user_bookmark(user_id, manga_name, chapter)
    if success:
        update.message.reply_text(f"📌 Bookmarked: <b>{html.escape(manga_name)}</b> Chapter {chapter} ✅", parse_mode="HTML")
    else:
        update.message.reply_text("⚠️ Failed to save bookmark.")


# 📚 /mybookmarks
def mybookmarks_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    bookmarks = get_user_bookmarks(user_id)

    if not bookmarks:
        update.message.reply_text("📖 You have no bookmarks saved yet! Use <code>/bookmark &lt;manga&gt; &lt;chapter&gt;</code> to add one.", parse_mode="HTML")
        return

    buttons = []
    for idx, entry in enumerate(bookmarks):
        manga_name = entry.get("manga") or entry.get("name") or "Unknown"
        chap = entry.get("chapter", "-")
        label = f"{manga_name} (Ch. {chap})"
        # Safe callback data using index and user_id (stateless, survives restarts)
        buttons.append([InlineKeyboardButton(label, callback_data=f"bm_view_{idx}_{user_id}")])

    update.message.reply_text(
        "📚 <b>Your Saved Bookmarks:</b>\nTap any title to view details or remove it.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# 🧹 /clearbookmarks
def clearbookmarks_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    result = clear_user_bookmarks(user_id)
    if result:
        update.message.reply_text("🧹 All your bookmarks have been cleared!")
    else:
        update.message.reply_text("📖 You had no bookmarks to clear.")


# 🔁 Inline button handler
def handle_bookmark_buttons(update: Update, context: CallbackContext):
    query = update.callback_query
    try:
        query.answer()
    except Exception:
        pass

    user_id = query.from_user.id
    data = query.data

    parts = data.split("_")
    if len(parts) < 4:
        # Handle legacy or malformed format
        return

    action = f"{parts[0]}_{parts[1]}"  # bm_view or bm_remove
    try:
        idx = int(parts[2])
        owner_id = int(parts[3])
    except ValueError:
        return

    if user_id != owner_id:
        query.answer("👀 This isn't your bookmark list.", show_alert=True)
        return

    bookmarks = get_user_bookmarks(user_id)
    if idx >= len(bookmarks):
        query.edit_message_text("⚠️ This bookmark is no longer available. Try /mybookmarks again.")
        return

    target_bm = bookmarks[idx]
    manga_name = target_bm.get("manga") or target_bm.get("name", "Unknown")
    chapter = target_bm.get("chapter", "-")

    if action == "bm_remove":
        remove_bookmark(user_id, manga_name)
        try:
            query.edit_message_text(f"🗑️ Removed bookmark for <b>{html.escape(manga_name)}</b>.", parse_mode="HTML")
        except Exception:
            pass

    elif action == "bm_view":
        manga_list = search_manga_by_name(manga_name)
        manga = manga_list[0] if manga_list else None

        image = manga.get("image") if manga else None
        total_chapters = manga.get("total_chapters") if manga else None
        channel_link = (manga.get("channel_link") if manga else target_bm.get("channel_link")) or "https://t.me"

        try:
            ch = int(chapter)
            percent = round((ch / total_chapters) * 100) if total_chapters else 0
            percent = min(percent, 100)
            progress_text = f"📊 <b>Progress:</b> Chapter {ch} of {total_chapters} ({percent}%)" if total_chapters else "📊 <b>Progress:</b> Tracked"
        except Exception:
            progress_text = "📊 <b>Progress:</b> Tracked"

        direct_link = target_bm.get("post_link") or channel_link

        caption = (
            f"📚 <b>{html.escape(manga_name)}</b>\n\n"
            f"📖 <b>Your Current Chapter:</b> {chapter}\n"
            f"{progress_text}\n"
            f"🔗 <a href='{direct_link}'>Jump to Chapter {chapter}</a>"
        )

        buttons = [
            [InlineKeyboardButton(f"📖 Read Chapter {chapter}", url=direct_link)],
            [InlineKeyboardButton("❌ Remove Bookmark", callback_data=f"bm_remove_{idx}_{user_id}")]
        ]

        try:
            if image:
                query.message.delete()
                context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=image,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            else:
                query.edit_message_text(
                    caption,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(buttons),
                    disable_web_page_preview=True
                )
        except Exception:
            query.edit_message_text(caption, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))
