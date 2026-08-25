import html
import logging
from uuid import uuid4
from telegram import (
    InlineQueryResultArticle,
    InlineQueryResultCachedPhoto,
    InputTextMessageContent,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from database import (
    search_manga_by_name,
    get_all_manga_cached,
    get_user_manga_status,
    get_user_manga_lists,
    get_user_bookmarks,
    get_user_subscriptions,
    get_user_badges,
    get_manga_by_id,
    get_manga_rating_summary,
    get_all_ratings_cached
)
from config import WEB_APP_URL

logger = logging.getLogger(__name__)


def _format_shelf_text(shelf_name: str, emoji: str, channel_ids: list) -> str:
    if not channel_ids:
        return f"{emoji} <b>Your {shelf_name}:</b>\n\n<i>No manga added to this shelf yet!</i>"
    lines = [f"{emoji} <b>Your {shelf_name} ({len(channel_ids)} titles):</b>\n"]
    for cid in channel_ids[:50]:  # Limit to 50 for message size safety
        info = get_manga_by_id(cid)
        if info:
            name = html.escape(info.get("name", "Unknown"))
            link = info.get("channel_link") or f"https://t.me/c/{str(cid)[4:]}/1"
            chaps = info.get("total_chapters")
            ch_info = f" ({chaps} ch)" if chaps else ""
            lines.append(f"• <a href='{link}'>{name}</a>{ch_info}")
        else:
            lines.append(f"• Manga ID: <code>{cid}</code>")
    if len(channel_ids) > 50:
        lines.append(f"\n<i>...and {len(channel_ids) - 50} more titles!</i>")
    return "\n".join(lines)


def _format_hub_overview(user_name: str, lists: dict, bookmarks: list, subs: list, badges: list) -> str:
    read_count = len(lists.get("read", []))
    fav_count = len(lists.get("favorite", []))
    comp_count = len(lists.get("completed", []))
    hold_count = len(lists.get("hold", []))
    drop_count = len(lists.get("dropped", []))
    sub_count = len(subs)
    bm_count = len(bookmarks)
    badge_str = " ".join(badges) if badges else "🎖️ Explorer"

    return (
        f"🛸 <b>{html.escape(user_name)}'s Personal Manga Hub</b> 🌌\n\n"
        f"🏅 <b>Badges:</b> {badge_str}\n\n"
        f"📊 <b>Reading Shelves:</b>\n"
        f"• 🔔 Subscribed Alerts: <b>{sub_count}</b> titles\n"
        f"• 📖 Read: <b>{read_count}</b> titles\n"
        f"• ❤️ Favorites: <b>{fav_count}</b> titles\n"
        f"• 🏁 Completed: <b>{comp_count}</b> titles\n"
        f"• ⏸️ On Hold: <b>{hold_count}</b> titles\n"
        f"• 👋 Dropped: <b>{drop_count}</b> titles\n"
        f"• 📌 Bookmarks: <b>{bm_count}</b> chapters\n\n"
        f"<i>Tap below to open your interactive hub in the bot or browse the Web Mini App!</i>"
    )


def inline_query(update, context):
    if not update.inline_query:
        return

    query_text = (update.inline_query.query or "").strip()
    raw_offset = update.inline_query.offset or ""
    offset = int(raw_offset) if raw_offset.isdigit() else 0
    PAGE_SIZE = 50

    user = update.inline_query.from_user
    user_id = user.id
    user_name = user.full_name or "Reader"
    bot_username = context.bot.username or "Galactic_Update_bot"
    results = []

    try:
        q_lower = query_text.lower()
        is_bookmark_query = q_lower in ["bm", "bookmark", "bookmarks", "mybookmarks", "reading", "continue"]
        is_hub_query = q_lower in [
            "hub", "myhub", "webhub", "web_hub", "web", "catalog", "me", "shelves", "shelf", "list",
            "fav", "favorite", "favorites", "read", "completed",
            "hold", "drop", "dropped",
            "sub", "subs", "subscribed", "subscription", "subscriptions"
        ]

        # Fast in-memory cached lookups (<1ms)
        lists = get_user_manga_lists(user_id)
        bookmarks = get_user_bookmarks(user_id)
        sub_ids = get_user_subscriptions(user_id)
        badges = get_user_badges(user_id)
        all_ratings = get_all_ratings_cached()

        user_shelf_map = {}
        for stat_name, cids in lists.items():
            for cid in cids:
                user_shelf_map.setdefault(cid, []).append(stat_name)

        # -------------------------------------------------------------
        # 📌 1. BOOKMARK SEARCH (When user types "bm" or "bookmark")
        # -------------------------------------------------------------
        if is_bookmark_query:
            if not bookmarks:
                results.append(
                    InlineQueryResultArticle(
                        id="no_bookmarks_found",
                        title="📌 No Active Bookmarks",
                        description="You haven't saved any chapters yet! Use /bookmark <name> <ch> in bot.",
                        thumbnail_url="https://img.icons8.com/color/96/bookmark-ribbon.png",
                        input_message_content=InputTextMessageContent(
                            "📌 <b>No bookmarks found!</b>\n\nSave your reading progress using <code>/bookmark &lt;name&gt; &lt;ch&gt;</code> or tap <b>Bookmark</b> inside the Web Reader.",
                            parse_mode="HTML"
                        )
                    )
                )
            else:
                for b in bookmarks:
                    b_manga_name = b.get("manga") or b.get("name", "Unknown")
                    b_ch = b.get("chapter", 1)
                    b_cid = b.get("channel_id")
                    b_link = b.get("post_link") or (f"https://t.me/c/{str(b_cid)[4:]}/1" if b_cid else "https://t.me")
                    reader_url = f"https://t.me/{bot_username}?start=read_{b_cid}_{b_ch}" if b_cid else f"{WEB_APP_URL}/reader"

                    bm_kb = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton(f"📖 Continue Ch. {b_ch}", url=reader_url),
                            InlineKeyboardButton("Channel Post", url=b_link)
                        ],
                        [
                            InlineKeyboardButton("🛸 My Web Hub", url=f"https://t.me/{bot_username}?start=webhub")
                        ]
                    ])

                    caption = (
                        f"📌 <b>{html.escape(b_manga_name)}</b> — <b>Chapter {b_ch}</b>\n\n"
                        f"<i>Saved bookmark for {html.escape(user_name)}. Tap below to continue reading!</i>"
                    )

                    thumb = f"{WEB_APP_URL}/api/image/{b_cid}" if b_cid else "https://img.icons8.com/color/96/bookmark-ribbon.png"
                    results.append(
                        InlineQueryResultArticle(
                            id=f"bm_{b_cid}_{b_ch}",
                            title=f"📌 {b_manga_name} — Ch. {b_ch}",
                            description=f"Continue reading from Chapter {b_ch}",
                            thumbnail_url=thumb,
                            input_message_content=InputTextMessageContent(
                                caption,
                                parse_mode="HTML",
                                disable_web_page_preview=False
                            ),
                            reply_markup=bm_kb
                        )
                    )

            update.inline_query.answer(
                results,
                cache_time=1,
                is_personal=True,
                switch_pm_text="📌 Manage Bookmarks in Hub",
                switch_pm_parameter="mybookmarks"
            )
            return

        # -------------------------------------------------------------
        # 🛸 2. PERSONAL READING HUB & SHELVES (When user types "hub" or "myhub")
        # -------------------------------------------------------------
        if is_hub_query:
            read_ids = lists.get("read", [])
            fav_ids = lists.get("favorite", [])
            comp_ids = lists.get("completed", [])
            hold_ids = lists.get("hold", [])
            drop_ids = lists.get("dropped", [])

            hub_keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🌌 Launch Web Hub", url=f"https://t.me/{bot_username}?start=webhub"),
                    InlineKeyboardButton("📚 Web Catalog", url=f"https://t.me/{bot_username}?start=web")
                ],
                [
                    InlineKeyboardButton("🛸 Open Bot Hub", url=f"https://t.me/{bot_username}?start=hub"),
                    InlineKeyboardButton("🔍 Search Manga", url=f"https://t.me/{bot_username}?start=search")
                ]
            ])

            # Hub Overview Card
            results.append(
                InlineQueryResultArticle(
                    id="hub_main_overview",
                    title="🛸 My Personal Web Hub & Shelves",
                    description=f"📖 {len(read_ids)} Read • ❤️ {len(fav_ids)} Fav • 🔔 {len(sub_ids)} Subs • 📌 {len(bookmarks)} Bookmarks",
                    thumbnail_url="https://img.icons8.com/color/96/planet.png",
                    input_message_content=InputTextMessageContent(
                        _format_hub_overview(user_name, lists, bookmarks, sub_ids, badges),
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    ),
                    reply_markup=hub_keyboard
                )
            )

            # Shelf: Bookmarks
            bm_lines = []
            for b in bookmarks[:25]:
                b_manga = html.escape(b.get("manga", "Unknown"))
                b_ch = b.get("chapter", 1)
                b_link = b.get("post_link")
                if b_link:
                    bm_lines.append(f"• <a href='{b_link}'>{b_manga}</a> — <b>Ch. {b_ch}</b>")
                else:
                    bm_lines.append(f"• <b>{b_manga}</b> — Ch. {b_ch}")
            bm_text = f"📌 <b>Your Bookmarks ({len(bookmarks)} chapters):</b>\n\n" + (
                "\n".join(bm_lines) if bm_lines else "<i>No active bookmarks! Use /bookmark &lt;name&gt; &lt;ch&gt; to add one.</i>"
            )
            results.append(
                InlineQueryResultArticle(
                    id="hub_bms",
                    title=f"📌 My Bookmarks ({len(bookmarks)} chapters)",
                    description="Direct links to your saved chapter progress",
                    thumbnail_url="https://img.icons8.com/color/96/bookmark-ribbon.png",
                    input_message_content=InputTextMessageContent(
                        bm_text,
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    ),
                    reply_markup=hub_keyboard
                )
            )

            # Shelf: Subscriptions
            results.append(
                InlineQueryResultArticle(
                    id="hub_subs",
                    title=f"🔔 Subscribed Alerts ({len(sub_ids)} titles)",
                    description="Manga you receive new chapter notifications for",
                    thumbnail_url="https://img.icons8.com/color/96/bell--v1.png",
                    input_message_content=InputTextMessageContent(
                        _format_shelf_text("Subscribed Alerts", "🔔", sub_ids),
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    ),
                    reply_markup=hub_keyboard
                )
            )

            # Shelf: Favorites
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
                    ),
                    reply_markup=hub_keyboard
                )
            )

            update.inline_query.answer(
                results,
                cache_time=1,
                is_personal=True,
                switch_pm_text="🔍 Search All Manga Titles",
                switch_pm_parameter="search"
            )
            return

        # -------------------------------------------------------------
        # 📚 3. COMPLETE 127+ MANGA CATALOG & SEARCH (With Pagination)
        # -------------------------------------------------------------
        all_manga = get_all_manga_cached()

        if not query_text:
            # Full library sorted A-Z
            all_matches = sorted(all_manga, key=lambda x: x.get("name", "").strip().lower())
        else:
            # Full Fuzzy + Substring match across all 127+ titles
            all_matches = search_manga_by_name(query_text, limit=150, cutoff=35)

        # Slice current page with next_offset
        total_items = len(all_matches)
        page_items = all_matches[offset : offset + PAGE_SIZE]
        next_offset = str(offset + PAGE_SIZE) if (offset + PAGE_SIZE) < total_items else ""

        # Prepend quick Hub card on initial empty search at offset 0
        if not query_text and offset == 0:
            read_ids = lists.get("read", [])
            fav_ids = lists.get("favorite", [])
            results.append(
                InlineQueryResultArticle(
                    id="hub_quick_card",
                    title=f"🛸 {user_name}'s Reading Hub",
                    description=f"📊 {len(read_ids)} Read • ❤️ {len(fav_ids)} Fav • 📌 {len(bookmarks)} Bookmarks",
                    thumbnail_url="https://img.icons8.com/color/96/planet.png",
                    input_message_content=InputTextMessageContent(
                        _format_hub_overview(user_name, lists, bookmarks, sub_ids, badges),
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    ),
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("🌌 Launch Web Hub", url=f"https://t.me/{bot_username}?start=webhub"),
                            InlineKeyboardButton("📚 Web Catalog", url=f"https://t.me/{bot_username}?start=web")
                        ]
                    ])
                )
            )

        for manga in page_items:
            raw_name = manga.get("name", "Unknown Title")
            title = raw_name.title()
            channel_id = manga.get("channel_id")
            channel_link = manga.get("channel_link") or f"https://t.me/c/{str(channel_id)[4:]}/1"
            total_chapters = manga.get("total_chapters")
            cover_image = f"{WEB_APP_URL}/api/image/{channel_id}"

            # In-memory status tags
            status_list = user_shelf_map.get(channel_id, []) if channel_id else []
            status_tags = []
            if "favorite" in status_list: status_tags.append("❤️ Fav")
            if "read" in status_list: status_tags.append("✅ Read")
            if "completed" in status_list: status_tags.append("🏁 Completed")
            if "hold" in status_list: status_tags.append("⏸️ Hold")
            if "dropped" in status_list: status_tags.append("👋 Dropped")

            status_str = " | ".join(status_tags) if status_tags else "Not tracked"
            chap_str = f" • {total_chapters} ch" if total_chapters else ""
            description = f"{status_str}{chap_str}"

            # In-memory ratings
            rating_data = all_ratings.get(channel_id, {"avg_rating": 0.0, "total_ratings": 0}) if channel_id else {}
            avg = rating_data.get("avg_rating", 0.0)
            count = rating_data.get("total_ratings", 0)
            stars_str = f"⭐ <b>{avg}/5.0</b> ({count} reviews)" if count > 0 else "⭐ <i>No ratings yet</i>"

            safe_title = html.escape(title)
            caption_text = (
                f"📚 <b>{safe_title}</b>\n"
                f"{stars_str}\n"
                f"📖 <b>Total Chapters:</b> {total_chapters or 'Ongoing'}\n"
                f"📌 <b>Your Shelf:</b> {status_str}\n\n"
                f"<i>Tap below to read in Telegram channel or launch the live Web Reader:</i>"
            )

            buttons = [
                [
                    InlineKeyboardButton("📖 Read in Channel", url=channel_link),
                    InlineKeyboardButton("🌐 Web Reader", url=f"https://t.me/{bot_username}?start=read_{channel_id}_1")
                ],
                [
                    InlineKeyboardButton("🛸 Web Hub", url=f"https://t.me/{bot_username}?start=webhub"),
                    InlineKeyboardButton("📌 View in Bot", url=f"https://t.me/{bot_username}?start=manga_{channel_id}")
                ]
            ]

            img_file_id = manga.get("image") or manga.get("image_id") or manga.get("banner") or manga.get("photo")
            if img_file_id and isinstance(img_file_id, str) and not img_file_id.startswith("http") and len(img_file_id) > 20:
                results.append(
                    InlineQueryResultCachedPhoto(
                        id=f"manga_{channel_id}_{offset}",
                        photo_file_id=img_file_id,
                        title=title,
                        description=description,
                        caption=caption_text,
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                )
            else:
                results.append(
                    InlineQueryResultArticle(
                        id=f"manga_{channel_id}_{offset}",
                        title=title,
                        description=description,
                        thumbnail_url=cover_image,
                        thumbnail_width=100,
                        thumbnail_height=140,
                        input_message_content=InputTextMessageContent(
                            caption_text,
                            parse_mode="HTML",
                            disable_web_page_preview=False
                        ),
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                )

        if not results:
            no_match_text = (
                f"🔍 <b>No manga found for:</b> <code>{html.escape(query_text)}</code>\n\n"
                f"• Check the spelling or try a shorter keyword\n"
                f"• Request this manga from the admins: <code>/request {html.escape(query_text)}</code>\n"
                f"• Or explore the full catalog with <code>/web</code>"
            )
            results.append(
                InlineQueryResultArticle(
                    id="no_manga_found",
                    title=f"❌ No manga found for '{query_text}'",
                    description="Tap to send request info or browse catalog",
                    thumbnail_url="https://img.icons8.com/color/96/search--v1.png",
                    input_message_content=InputTextMessageContent(
                        no_match_text,
                        parse_mode="HTML"
                    ),
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("📨 Request in Bot", url=f"https://t.me/{bot_username}?start=request"),
                            InlineKeyboardButton("🌐 Browse Catalog", url=f"{WEB_APP_URL}/web")
                        ]
                    ])
                )
            )

        update.inline_query.answer(
            results[:50],
            cache_time=1,
            is_personal=True,
            next_offset=next_offset,
            switch_pm_text=f"🛸 127+ Manga Catalog (Total: {total_items})",
            switch_pm_parameter="webhub"
        )
    except Exception as e:
        logger.error(f"[INLINE ERROR] {e}", exc_info=True)
        try:
            update.inline_query.answer([], cache_time=1)
        except Exception:
            pass

