import html
from uuid import uuid4
from telegram import (
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from database import search_manga_by_name, get_user_manga_status


def inline_query(update, context):
    query_text = update.inline_query.query.strip()
    user_id = update.inline_query.from_user.id

    if not query_text:
        update.inline_query.answer([], cache_time=10)
        return

    search_results = search_manga_by_name(query_text, limit=10)
    results = []

    for manga in search_results:
        raw_name = manga.get("name", "Unknown Title")
        title = raw_name.title()
        channel_id = manga.get("channel_id")
        channel_link = manga.get("channel_link") or f"https://t.me/c/{str(channel_id)[4:]}/1"
        total_chapters = manga.get("total_chapters")

        # User reading status tags
        status_list = get_user_manga_status(user_id, channel_id) if channel_id else []
        status_text = []
        if "read" in status_list:
            status_text.append("✅ Read")
        if "favorite" in status_list:
            status_text.append("❤️ Favorite")
        if "completed" in status_list:
            status_text.append("🏁 Completed")
        if "dropped" in status_list:
            status_text.append("👋 Dropped")
        if "hold" in status_list:
            status_text.append("⏸️ On Hold")

        status_str = " | ".join(status_text) if status_text else "Not tracked yet"
        chap_str = f" • {total_chapters} chapters" if total_chapters else ""
        description = f"{status_str}{chap_str}"

        safe_title = html.escape(title)
        message_content = (
            f"📚 <b>{safe_title}</b>\n\n"
            f"🔗 <a href='{channel_link}'>Open Manga Channel</a>\n"
            f"📌 <b>Your Status:</b> {status_str}"
        )

        results.append(
            InlineQueryResultArticle(
                id=str(uuid4()),
                title=title,
                description=description,
                input_message_content=InputTextMessageContent(
                    message_content,
                    parse_mode="HTML",
                    disable_web_page_preview=False
                )
            )
        )

    update.inline_query.answer(results, cache_time=5, is_personal=True)
