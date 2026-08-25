import html
import logging
from uuid import uuid4
from telegram import (
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo
)
from database import (
    search_manga_by_name,
    get_all_manga_cached,
    get_user_manga_status,
    get_user_manga_lists,
    get_user_bookmarks,
    get_manga_by_id,
    get_manga_rating_summary
)
from config import WEB_APP_URL

logger = logging.getLogger(__name__)


def _format_shelf_text(shelf_name: str, emoji: str, channel_ids: list) -> str:
    if not channel_ids:
        return f"{emoji} <b>Your {shelf_name}:</b>\n\n<i>No manga added to this shelf yet!</i>"
    lines = [f"{emoji} <b>Your {shelf_name} ({len(channel_ids)}):</b>\n"]
    for cid in channel_ids:
        info = get_manga_by_id(cid)
        if info:
            name = html.escape(info.get("name", "Unknown"))
            link = info.get("channel_link") or f"https://t.me/c/{str(cid)[4:]}/1"
            chaps = info.get("total_chapters")
            ch_info = f" ({chaps} ch)" if chaps else ""
            lines.append(f"• <a href='{link}'>{name}</a>{ch_info}")
        else:
            lines.append(f"• Manga ID: {cid}")
    return "\n".join(lines)


def inline_query(update, context):
    if not update.inline_query:
        return

    query_text = (update.inline_query.query or "").strip()
    user_id = update.inline_query.from_user.id
    results = []

    try:
        # =========================================================
        # 🛸 1. PERSONAL READING HUB (hub, myhub, me, shelves, read, fav)
        # =========================================================
        q_lower = query_text.lower()
        if q_lower in ["hub", "myhub", "me", "shelves", "shelf", "list", "fav", "read", "bookmarks", "bookmark"]:
            lists = get_user_manga_lists(user_id)
            bookmarks = get_user_bookmarks(user_id)

            read_ids = lists.get("read", [])
            fav_ids = lists.get("favorite", [])
            comp_ids = lists.get("completed", [])
            hold_ids = lists.get("hold", [])
            drop_ids = lists.get("dropped", [])

            # Shelf 1: Read List
            results.append(
                InlineQueryResultArticle(
                    id="hub_read",
                    title=f"📖 My Read Shelf ({len(read_ids)} titles)",
                    description="View all manga you've marked as read",
                    thumbnail_url="https://img.icons8.com/color/96/book-stack.png",
                    input_message_content=InputTextMessageContent(
                        _format_shelf_text("Read Shelf", "📖", read_ids),
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                )
            )

            # Shelf 2: Favorites
            results.append(
                InlineQueryResultArticle(
                    id="hub_fav",
                    title=f"❤️ My Favorites ({len(fav_ids)} titles)",
                    description="View your favorite manga collection",
                    thumbnail_url="https://img.icons8.com/color/96/like--v1.png",
                    input_message_content=InputTextMessageContent(
                        _format_shelf_text("Favorites", "❤️", fav_ids),
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                )
            )

            # Shelf 3: Completed
            results.append(
                InlineQueryResultArticle(
                    id="hub_comp",
                    title=f"🏁 Completed Manga ({len(comp_ids)} titles)",
                    description="Manga you've finished reading",
                    thumbnail_url="https://img.icons8.com/color/96/finish-flag.png",
                    input_message_content=InputTextMessageContent(
                        _format_shelf_text("Completed List", "🏁", comp_ids),
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                )
            )

            # Shelf 4: On Hold
            results.append(
                InlineQueryResultArticle(
                    id="hub_hold",
                    title=f"⏸️ On Hold Manga ({len(hold_ids)} titles)",
                    description="Manga paused for later",
                    thumbnail_url="https://img.icons8.com/color/96/pause-button.png",
                    input_message_content=InputTextMessageContent(
                        _format_shelf_text("On Hold Shelf", "⏸️", hold_ids),
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                )
            )

            # Shelf 5: Dropped
            results.append(
                InlineQueryResultArticle(
                    id="hub_drop",
                    title=f"👋 Dropped Manga ({len(drop_ids)} titles)",
                    description="Manga you decided to drop",
                    thumbnail_url="https://img.icons8.com/color/96/trash--v1.png",
                    input_message_content=InputTextMessageContent(
                        _format_shelf_text("Dropped Shelf", "👋", drop_ids),
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                )
            )

            # Shelf 6: Bookmarks
            bm_lines = []
            for b in bookmarks:
                b_manga = html.escape(b.get("manga", "Unknown"))
                b_ch = b.get("chapter", 1)
                b_link = b.get("post_link")
                if b_link:
                    bm_lines.append(f"• <a href='{b_link}'>{b_manga}</a> — Ch. {b_ch}")
                else:
                    bm_lines.append(f"• <b>{b_manga}</b> — Ch. {b_ch}")
            bm_text = f"📌 <b>Your Bookmarks ({len(bookmarks)}):</b>\n\n" + ("\n".join(bm_lines) if bm_lines else "<i>No active bookmarks!</i>")

            results.append(
                InlineQueryResultArticle(
                    id="hub_bms",
                    title=f"📌 My Bookmarks ({len(bookmarks)} chapters)",
                    description="Direct chapter links to your saved progress",
                    thumbnail_url="https://img.icons8.com/color/96/bookmark-ribbon.png",
                    input_message_content=InputTextMessageContent(
                        bm_text,
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                )
            )

            update.inline_query.answer(results, cache_time=3, is_personal=True)
            return

        # =========================================================
        # 📚 2. MANGA CATALOG & SEARCH RESULTS
        # =========================================================
        if not query_text:
            # Empty query -> Show top popular / active manga from catalog (up to 40)
            all_manga = get_all_manga_cached()
            search_results = sorted(all_manga, key=lambda x: int(x.get("total_chapters") or 0), reverse=True)[:40]
        else:
            # Search query -> Run hybrid search
            search_results = search_manga_by_name(query_text, limit=30)

        for manga in search_results:
            raw_name = manga.get("name", "Unknown Title")
            title = raw_name.title()
            channel_id = manga.get("channel_id")
            channel_link = manga.get("channel_link") or f"https://t.me/c/{str(channel_id)[4:]}/1"
            total_chapters = manga.get("total_chapters")
            cover_image = f"{WEB_APP_URL}/api/image/{channel_id}"

            # Reading status tags for the querying user
            status_list = get_user_manga_status(user_id, channel_id) if channel_id else []
            status_tags = []
            if "favorite" in status_list: status_tags.append("❤️ Fav")
            if "read" in status_list: status_tags.append("✅ Read")
            if "completed" in status_list: status_tags.append("🏁 Completed")
            if "hold" in status_list: status_tags.append("⏸️ Hold")
            if "dropped" in status_list: status_tags.append("👋 Dropped")

            status_str = " | ".join(status_tags) if status_tags else "Not tracked"
            chap_str = f" • {total_chapters} ch" if total_chapters else ""
            description = f"{status_str}{chap_str}"

            # Ratings
            rating_data = get_manga_rating_summary(channel_id, user_id) if channel_id else {}
            avg = rating_data.get("avg_rating", 0.0)
            count = rating_data.get("total_ratings", 0)
            stars_str = f"⭐ <b>{avg}/5.0</b> ({count} reviews)" if count > 0 else "⭐ <i>No ratings yet</i>"

            safe_title = html.escape(title)
            message_content = (
                f"📚 <b>{safe_title}</b>\n"
                f"{stars_str}\n"
                f"📖 <b>Total Chapters:</b> {total_chapters or 'Ongoing'}\n"
                f"📌 <b>Your Shelf:</b> {status_str}\n\n"
                f"<i>Tap below to read all chapters directly in Telegram or in the Live Web Reader:</i>"
            )

            buttons = [
                [
                    InlineKeyboardButton("📖 Read in Channel", url=channel_link),
                    InlineKeyboardButton("🌐 Web Reader", web_app=WebAppInfo(url=f"{WEB_APP_URL}/reader?channel_id={channel_id}&ch=1"))
                ]
            ]

            results.append(
                InlineQueryResultArticle(
                    id=str(uuid4()),
                    title=title,
                    description=description,
                    thumbnail_url=cover_image,
                    thumbnail_width=100,
                    thumbnail_height=140,
                    input_message_content=InputTextMessageContent(
                        message_content,
                        parse_mode="HTML",
                        disable_web_page_preview=False
                    ),
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            )

        update.inline_query.answer(results, cache_time=5, is_personal=True)
    except Exception as e:
        logger.error(f"[INLINE ERROR] {e}", exc_info=True)
        try:
            update.inline_query.answer([], cache_time=2)
        except Exception:
            pass

