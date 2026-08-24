from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext, CallbackQueryHandler, CommandHandler
from database import manga_col, is_sudo

PAGE_SIZE = 6

def list_manga(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not is_sudo(user_id):
        update.message.reply_text("⛔ Only sudo users can view the full manga list.")
        return

    send_manga_page(update, context, page=0)

def send_manga_page(update, context, page):
    all_manga = list(manga_col.find({}).sort("name"))
    total = len(all_manga)
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    current_page_manga = all_manga[start:end]

    if not current_page_manga:
        update.message.reply_text("📭 No manga found.")
        return

    text = "<b>📚 Manga List:</b>\n\n"
    for i, manga in enumerate(current_page_manga, start=start + 1):
        name = manga.get("name", "Unknown")
        channel_link = manga.get("channel_link")

        if channel_link:
            text += f"{i}. <a href='{channel_link}'>{name}</a>\n"
        else:
            text += f"{i}. {name}\n"

    # Pagination buttons
    buttons = []
    if start > 0:
        buttons.append(InlineKeyboardButton("⬅ Prev", callback_data=f"listmanga_page_{page-1}"))
    if end < total:
        buttons.append(InlineKeyboardButton("Next ➡", callback_data=f"listmanga_page_{page+1}"))

    if update.message:
        update.message.reply_text(
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([buttons]) if buttons else None
        )
    else:
        update.callback_query.edit_message_text(
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([buttons]) if buttons else None
        )


def list_manga_page_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    user_id = query.from_user.id
    if not is_sudo(user_id):
        query.edit_message_text("⛔ You're not allowed to view this.")
        return

    try:
        page = int(query.data.split("_")[-1])
        send_manga_page(update, context, page)
    except:
        query.edit_message_text("⚠️ Failed to load manga page.")

def register_listmanga_handlers(dp):
    dp.add_handler(CommandHandler("listmanga", list_manga))
    dp.add_handler(CallbackQueryHandler(list_manga_page_callback, pattern=r"^listmanga_page_\d+$"))
