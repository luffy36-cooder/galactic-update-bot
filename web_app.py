import os
import logging
from flask import request, jsonify, render_template, redirect, Response, send_file
from database import (
    manga_col,
    ratings_col,
    get_manga_by_id,
    get_user_manga_status,
    get_user_manga_lists,
    get_user_bookmarks,
    get_user_profile,
    get_user_badges,
    update_manga_status,
    save_user_bookmark,
    remove_bookmark,
    mark_chapter_as_read,
    read_log_col,
    save_manga_rating,
    get_manga_rating_summary,
    get_manga_reviews,
    subscribe_manga,
    unsubscribe_manga,
    is_user_subscribed,
    get_user_subscriptions,
    get_chapter_file,
    get_manga_chapter_list,
    get_all_manga_cached,
)
from profile_handler import get_rank_title

logger = logging.getLogger(__name__)

# SVG fallback placeholder for manga without covers
DEFAULT_COVER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="300" height="420" viewBox="0 0 300 420">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#181926"/>
      <stop offset="100%" stop-color="#0b0c13"/>
    </linearGradient>
    <linearGradient id="accent" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#a855f7"/>
      <stop offset="100%" stop-color="#6366f1"/>
    </linearGradient>
  </defs>
  <rect width="300" height="420" fill="url(#bg)" rx="16"/>
  <rect x="15" y="15" width="270" height="390" fill="none" stroke="#2a2b3d" stroke-width="2" rx="12"/>
  <circle cx="150" cy="180" r="55" fill="url(#accent)" opacity="0.15"/>
  <text x="150" y="195" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="50" text-anchor="middle">📖</text>
  <text x="150" y="270" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="16" font-weight="600" fill="#9ca3af" text-anchor="middle">MANGA GALACTIC</text>
</svg>"""


def register_web_routes(app, bot_getter=None):
    """Registers all Web App routes and REST API endpoints on the Flask application."""

    # -------------------------------------------------------------
    # 🌐 HTML Pages
    # -------------------------------------------------------------
    @app.route("/web")
    @app.route("/catalog")
    @app.route("/mangaweb")
    def web_catalog():
        return render_template("index.html")

    @app.route("/webhub")
    @app.route("/hub")
    @app.route("/myhub")
    @app.route("/webprofile")
    @app.route("/myprofile")
    @app.route("/profile")
    def web_profile():
        return render_template("profile.html")

    @app.route("/reader")
    @app.route("/read")
    def web_reader():
        return render_template("reader.html")

    @app.route("/static/images/default_cover.svg")
    def default_cover():
        return Response(DEFAULT_COVER_SVG, mimetype="image/svg+xml")

    # -------------------------------------------------------------
    # 🖼️ Image Proxy Endpoint (Resolves Telegram file_id)
    # -------------------------------------------------------------
    _image_url_cache = {}  # img_val -> (url, timestamp)

    @app.route("/api/image/<int(signed=True):channel_id>")
    def get_image_proxy(channel_id):
        import time as _time
        manga = get_manga_by_id(channel_id)
        if not manga or not manga.get("image"):
            return Response(DEFAULT_COVER_SVG, mimetype="image/svg+xml")

        img_val = manga.get("image")
        if isinstance(img_val, str) and (img_val.startswith("http://") or img_val.startswith("https://")):
            return redirect(img_val)

        now = _time.time()
        cached = _image_url_cache.get(img_val)
        if cached and (now - cached[1]) < 3600:
            return redirect(cached[0])

        bot = bot_getter() if callable(bot_getter) else bot_getter
        if bot:
            try:
                tg_file = bot.get_file(img_val)
                if tg_file and tg_file.file_path:
                    _image_url_cache[img_val] = (tg_file.file_path, now)
                    return redirect(tg_file.file_path)
            except Exception as e:
                logger.warning(f"Failed to fetch Telegram image for {channel_id}: {e}")

        return Response(DEFAULT_COVER_SVG, mimetype="image/svg+xml")

    # -------------------------------------------------------------
    # 📦 API: Manga Catalog with User-Specific Status & Ratings
    # -------------------------------------------------------------
    @app.route("/api/manga", methods=["GET"])
    def api_get_manga():
        user_id_raw = request.args.get("user_id")
        user_id = int(user_id_raw) if user_id_raw and user_id_raw.isdigit() else None

        user_status_map = {}
        user_bookmarks_map = {}
        user_subs_set = set()
        user_ratings_map = {}

        if user_id:
            user_lists = get_user_manga_lists(user_id)
            for status_type, cids in user_lists.items():
                for cid in cids:
                    if cid not in user_status_map:
                        user_status_map[cid] = []
                    user_status_map[cid].append(status_type)

            bms = get_user_bookmarks(user_id)
            for b in bms:
                b_name = (b.get("manga") or b.get("name", "")).lower()
                user_bookmarks_map[b_name] = b.get("chapter", "")

            user_subs_set = set(get_user_subscriptions(user_id))

            # Batch load user ratings
            from database import ratings_col
            for doc in ratings_col.find({"user_id": user_id}, {"channel_id": 1, "rating": 1}):
                user_ratings_map[doc.get("channel_id")] = doc.get("rating")

        # Batch load all ratings in 1 single MongoDB aggregation
        from database import ratings_col
        pipeline = [
            {"$group": {
                "_id": "$channel_id",
                "avg_rating": {"$avg": "$rating"},
                "total_ratings": {"$sum": 1}
            }}
        ]
        all_ratings = {
            doc["_id"]: {
                "avg_rating": round(float(doc["avg_rating"]), 1),
                "total_ratings": int(doc["total_ratings"])
            }
            for doc in ratings_col.aggregate(pipeline)
        }

        is_user_admin = False
        if user_id:
            from database import is_sudo
            from config import BOT_OWNER_ID
            is_user_admin = (user_id == BOT_OWNER_ID) or is_sudo(user_id)

        all_manga = get_all_manga_cached()
        catalog = []

        for m in all_manga:
            cid = m.get("channel_id")
            name = m.get("name", "Unknown Title")
            has_image = bool(m.get("image"))
            image_url = f"/api/image/{cid}" if has_image else "/static/images/default_cover.svg"

            rating_summary = all_ratings.get(cid, {"avg_rating": 0.0, "total_ratings": 0})

            item = {
                "channel_id": cid,
                "name": name,
                "channel_link": m.get("channel_link") or (f"https://t.me/c/{str(cid)[4:]}/1" if cid else ""),
                "total_chapters": m.get("total_chapters") or 0,
                "image_url": image_url,
                "synopsis": m.get("synopsis") or "An epic story unfolding in Manga Galactic.",
                "genres": m.get("genres") or ["Action", "Fantasy", "Adventure"],
                "score": m.get("score") or 88,
                "manga_status": m.get("status") or "Releasing",
                "banner": m.get("banner"),
                "characters": m.get("characters") or [],
                "status": user_status_map.get(cid, []) if user_id else [],
                "bookmark_chapter": user_bookmarks_map.get(name.lower(), None) if user_id else None,
                "is_bookmarked": name.lower() in user_bookmarks_map if user_id else False,
                "is_subscribed": (cid in user_subs_set or (user_id and "favorite" in user_status_map.get(cid, []))),
                "avg_rating": rating_summary.get("avg_rating", 0.0),
                "total_ratings": rating_summary.get("total_ratings", 0),
                "user_rating": user_ratings_map.get(cid)
            }
            catalog.append(item)

        return jsonify({
            "success": True,
            "count": len(catalog),
            "manga": catalog,
            "is_admin": is_user_admin
        })

    # -------------------------------------------------------------
    # 🛡️ API: Admin Manga Edit (Admins Only)
    # -------------------------------------------------------------
    @app.route("/api/admin/edit_manga", methods=["POST"])
    def api_admin_edit_manga():
        data = request.get_json(force=True, silent=True) or {}
        user_id_raw = data.get("user_id")
        cid_raw = data.get("channel_id")

        if not user_id_raw or not cid_raw:
            return jsonify({"success": False, "error": "user_id and channel_id are required"}), 400

        try:
            user_id = int(user_id_raw)
            channel_id = int(cid_raw)
        except ValueError:
            return jsonify({"success": False, "error": "Invalid user_id or channel_id format"}), 400

        from database import is_sudo
        from config import BOT_OWNER_ID
        if not (user_id == BOT_OWNER_ID or is_sudo(user_id)):
            return jsonify({"success": False, "error": "Unauthorized: Admin privileges required"}), 403

        update_doc = {}
        if "name" in data and str(data["name"]).strip():
            update_doc["name"] = str(data["name"]).strip()
        if "synopsis" in data:
            update_doc["synopsis"] = str(data["synopsis"]).strip()
        if "genres" in data:
            genres_val = data["genres"]
            if isinstance(genres_val, list):
                update_doc["genres"] = [str(g).strip() for g in genres_val if str(g).strip()]
            elif isinstance(genres_val, str):
                update_doc["genres"] = [g.strip() for g in genres_val.split(",") if g.strip()]
        if "score" in data and data["score"] is not None:
            try:
                update_doc["score"] = int(data["score"])
            except (ValueError, TypeError):
                pass
        if "status" in data and str(data["status"]).strip():
            update_doc["status"] = str(data["status"]).strip()
        if "banner" in data:
            update_doc["banner"] = str(data["banner"]).strip() if data["banner"] else None
        if "total_chapters" in data and data["total_chapters"] is not None:
            try:
                update_doc["total_chapters"] = int(data["total_chapters"])
            except (ValueError, TypeError):
                pass

        if not update_doc:
            return jsonify({"success": False, "error": "No valid update fields provided"}), 400

        from database import manga_col, _invalidate_manga_cache
        manga_col.update_one({"channel_id": channel_id}, {"$set": update_doc})
        _invalidate_manga_cache()

        logger.info(f"🛡️ Admin {user_id} updated manga {channel_id}: {list(update_doc.keys())}")
        return jsonify({
            "success": True,
            "message": "Manga details saved successfully!",
            "updated": update_doc
        })

    # -------------------------------------------------------------
    # 👤 API: Reader Profile & Shelves
    # -------------------------------------------------------------
    @app.route("/api/profile", methods=["GET"])
    def api_get_profile():
        user_id_raw = request.args.get("user_id")
        if not user_id_raw or not user_id_raw.isdigit():
            return jsonify({"success": False, "error": "Valid user_id query parameter required"}), 400

        user_id = int(user_id_raw)
        profile_data = get_user_profile(user_id)
        badges = get_user_badges(user_id)
        manga_lists = get_user_manga_lists(user_id)
        bookmarks = get_user_bookmarks(user_id)
        subs = get_user_subscriptions(user_id)

        read_count = len(manga_lists.get("read", []))
        completed_count = len(manga_lists.get("completed", []))
        fav_count = len(manga_lists.get("favorite", []))
        drop_count = len(manga_lists.get("dropped", []))
        hold_count = len(manga_lists.get("hold", []))
        rank_title = get_rank_title(read_count)

        # Hydrate manga lists using in-memory cache for instant <10ms loading
        bms_map = { (b.get("manga") or b.get("name", "")).lower(): b.get("chapter") for b in bookmarks }
        user_ratings_map = { r["channel_id"]: r["rating"] for r in ratings_col.find({"user_id": user_id}, {"channel_id": 1, "rating": 1}) }
        all_manga_dict = { m["channel_id"]: m for m in get_all_manga_cached() if "channel_id" in m }

        hydrated_shelves = {}
        for shelf_name, cids in manga_lists.items():
            hydrated_shelves[shelf_name] = []
            for cid in cids:
                manga = all_manga_dict.get(cid) or get_manga_by_id(cid)
                if manga:
                    m_name = manga.get("name", "Unknown")
                    bm_chap = bms_map.get(m_name.lower())
                    hydrated_shelves[shelf_name].append({
                        "channel_id": cid,
                        "name": m_name,
                        "channel_link": manga.get("channel_link") or f"https://t.me/c/{str(cid)[4:]}/1",
                        "image_url": f"/api/image/{cid}" if manga.get("image") else "/static/images/default_cover.svg",
                        "total_chapters": manga.get("total_chapters"),
                        "bookmark_chapter": bm_chap,
                        "is_bookmarked": bool(bm_chap),
                        "is_subscribed": cid in subs,
                        "is_favorite": cid in manga_lists.get("favorite", []),
                        "is_read": cid in manga_lists.get("read", []),
                        "user_rating": user_ratings_map.get(cid, 5)
                    })

        return jsonify({
            "success": True,
            "profile": {
                "user_id": user_id,
                "bookmarks_count": len(bookmarks),
                "read_count": read_count,
                "completed_count": completed_count,
                "favorites_count": fav_count,
                "dropped_count": drop_count,
                "hold_count": hold_count,
                "subscriptions_count": len(subs),
                "rank": rank_title,
                "badges": badges,
                "bookmarks": bookmarks,
                "shelves": hydrated_shelves
            }
        })

    # -------------------------------------------------------------
    # 🔄 API: Toggle Reading Status
    # -------------------------------------------------------------
    @app.route("/api/status", methods=["POST"])
    def api_toggle_status():
        data = request.get_json(silent=True) or {}
        user_id = data.get("user_id")
        channel_id = data.get("channel_id")
        status_key = data.get("status")
        add = data.get("add", True)

        if not user_id or not channel_id or not status_key:
            return jsonify({"success": False, "error": "Missing user_id, channel_id, or status"}), 400

        try:
            user_id = int(user_id)
            channel_id = int(channel_id)
        except ValueError:
            return jsonify({"success": False, "error": "Invalid IDs"}), 400

        valid_statuses = {"read", "favorite", "completed", "dropped", "hold"}
        if status_key not in valid_statuses:
            return jsonify({"success": False, "error": "Invalid status value"}), 400

        update_manga_status(user_id, channel_id, status_key, add=add)

        if status_key == "read" and add:
            mark_chapter_as_read(user_id, channel_id, chapter_number=0)
        elif status_key == "read" and not add:
            read_log_col.update_one(
                {"user_id": user_id, "chapter": f"{channel_id}_0", "deleted": {"$ne": True}},
                {"$set": {"deleted": True}}
            )

        return jsonify({
            "success": True,
            "user_id": user_id,
            "channel_id": channel_id,
            "status": status_key,
            "added": add
        })

    # -------------------------------------------------------------
    # 📌 API: Save / Update Bookmark
    # -------------------------------------------------------------
    @app.route("/api/bookmark", methods=["POST"])
    def api_save_bookmark():
        data = request.get_json(silent=True) or {}
        user_id = data.get("user_id")
        manga_name = data.get("manga_name")
        chapter = data.get("chapter")

        if not user_id or not manga_name or chapter is None:
            return jsonify({"success": False, "error": "Missing user_id, manga_name, or chapter"}), 400

        try:
            user_id = int(user_id)
            chapter = int(chapter)
        except ValueError:
            return jsonify({"success": False, "error": "Invalid chapter or user_id"}), 400

        success = save_user_bookmark(user_id, manga_name, chapter)
        if not success:
            return jsonify({"success": False, "error": "Manga not found or failed to save"}), 404

        return jsonify({"success": True, "manga_name": manga_name, "chapter": chapter})

    # -------------------------------------------------------------
    # 🗑️ API: Remove Bookmark
    # -------------------------------------------------------------
    @app.route("/api/bookmark/remove", methods=["POST"])
    def api_remove_bookmark():
        data = request.get_json(silent=True) or {}
        user_id = data.get("user_id")
        manga_name = data.get("manga_name")

        if not user_id or not manga_name:
            return jsonify({"success": False, "error": "Missing user_id or manga_name"}), 400

        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({"success": False, "error": "Invalid user_id"}), 400

        remove_bookmark(user_id, manga_name)
        return jsonify({"success": True, "manga_name": manga_name})

    # -------------------------------------------------------------
    # ⭐ API: Rate Manga (1-5 Stars) & Optional Review
    # -------------------------------------------------------------
    @app.route("/api/rate", methods=["POST"])
    def api_rate_manga():
        data = request.get_json(silent=True) or {}
        user_id = data.get("user_id")
        user_name = data.get("user_name", "Anonymous")
        channel_id = data.get("channel_id")
        rating = data.get("rating")
        review = data.get("review")

        if not user_id or not channel_id or not rating:
            return jsonify({"success": False, "error": "Missing user_id, channel_id, or rating"}), 400

        try:
            user_id = int(user_id)
            channel_id = int(channel_id)
            rating = int(rating)
        except ValueError:
            return jsonify({"success": False, "error": "Invalid numerical parameters"}), 400

        save_manga_rating(user_id, user_name, channel_id, rating, review)
        summary = get_manga_rating_summary(channel_id, user_id)

        return jsonify({
            "success": True,
            "channel_id": channel_id,
            "rating": rating,
            "summary": summary
        })

    # -------------------------------------------------------------
    # 📝 API: Get Reviews for a Manga
    # -------------------------------------------------------------
    @app.route("/api/reviews/<int(signed=True):channel_id>", methods=["GET"])
    def api_get_reviews(channel_id):
        reviews = get_manga_reviews(channel_id, limit=10)
        summary = get_manga_rating_summary(channel_id)
        return jsonify({
            "success": True,
            "channel_id": channel_id,
            "summary": summary,
            "reviews": reviews
        })

    # -------------------------------------------------------------
    # 🔔 API: Toggle Chapter Alerts Subscription
    # -------------------------------------------------------------
    @app.route("/api/subscribe", methods=["POST"])
    def api_toggle_subscribe():
        data = request.get_json(silent=True) or {}
        user_id = data.get("user_id")
        channel_id = data.get("channel_id")
        sub_action = data.get("subscribe", True)

        if not user_id or not channel_id:
            return jsonify({"success": False, "error": "Missing user_id or channel_id"}), 400

        try:
            user_id = int(user_id)
            channel_id = int(channel_id)
        except ValueError:
            return jsonify({"success": False, "error": "Invalid IDs"}), 400

        if sub_action:
            subscribe_manga(user_id, channel_id)
        else:
            unsubscribe_manga(user_id, channel_id)

        return jsonify({
            "success": True,
            "user_id": user_id,
            "channel_id": channel_id,
            "subscribed": sub_action
        })

    # -------------------------------------------------------------
    # 📖 API: Get Manga Chapter List
    # -------------------------------------------------------------
    @app.route("/api/chapters/<int(signed=True):channel_id>", methods=["GET"])
    def api_get_chapters(channel_id):
        manga = get_manga_by_id(channel_id)
        if not manga:
            return jsonify({"success": False, "error": "Manga not found"}), 404

        chapters = get_manga_chapter_list(channel_id)
        return jsonify({
            "success": True,
            "channel_id": channel_id,
            "name": manga.get("name", "Manga"),
            "channel_link": manga.get("channel_link") or f"https://t.me/c/{str(channel_id)[4:]}/1",
            "total_chapters": manga.get("total_chapters") or len(chapters),
            "chapters": chapters
        })

    # -------------------------------------------------------------
    # 📄 API: Stream Chapter PDF directly from Telegram MTProto (Supports 20MB-2GB Files!)
    # -------------------------------------------------------------
    @app.route("/api/chapter/file/<int(signed=True):channel_id>/<int:chapter>", methods=["GET", "HEAD", "OPTIONS"])
    def api_get_chapter_file(channel_id, chapter):
        if request.method == "OPTIONS":
            resp = Response()
            resp.headers["Access-Control-Allow-Origin"] = "*"
            resp.headers["Access-Control-Allow-Methods"] = "GET, HEAD, OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = "Range, Content-Type, Accept"
            resp.headers["Access-Control-Expose-Headers"] = "Content-Range, Content-Length, Accept-Ranges"
            return resp

        chap_doc = get_chapter_file(channel_id, chapter)
        manga = get_manga_by_id(channel_id) or {}
        invite_link = manga.get("channel_link") or f"https://t.me/c/{str(channel_id)[4:]}/1"

        # On-Demand MTProto Auto-Scan if this chapter isn't indexed yet!
        if not chap_doc or not chap_doc.get("msg_id"):
            try:
                from tg_streamer import get_streamer
                streamer = get_streamer()
                highest_ch = manga.get("total_chapters", 0) or 0
                max_range = max(200, highest_ch + 50)
                streamer.scan_channel_batch(channel_id, start_id=1, end_id=max_range)
                chap_doc = get_chapter_file(channel_id, chapter)
            except Exception as e:
                logger.error(f"On-demand MTProto scan failed for channel {channel_id}: {e}")

        direct_post_link = invite_link
        if chap_doc and chap_doc.get("msg_id"):
            from channel_handler import build_post_link
            direct_post_link = build_post_link(channel_id, chap_doc["msg_id"], invite_link)

        if not chap_doc:
            return jsonify({
                "success": False,
                "error": f"Chapter {chapter} is not indexed yet.",
                "channel_link": direct_post_link
            }), 404

        # 1. Try local MTProto disk cache & fast range stream first
        msg_id = chap_doc.get("msg_id")
        if msg_id:
            try:
                from tg_streamer import get_streamer
                streamer = get_streamer()
                file_path = streamer.get_or_download_pdf(channel_id, msg_id)
                if file_path and os.path.exists(file_path):
                    resp = send_file(
                        file_path,
                        mimetype="application/pdf",
                        as_attachment=False,
                        download_name=f"Chapter_{chapter}.pdf",
                        conditional=True
                    )
                    resp.headers["Cache-Control"] = "public, max-age=604800, immutable"
                    resp.headers["Accept-Ranges"] = "bytes"
                    resp.headers["Access-Control-Allow-Origin"] = "*"
                    resp.headers["Access-Control-Allow-Headers"] = "Range, Content-Type, Accept"
                    resp.headers["Access-Control-Expose-Headers"] = "Content-Range, Content-Length, Accept-Ranges"
                    return resp
            except Exception as e:
                logger.debug(f"MTProto direct stream fallback: {e}")

        # 2. Try standard Telegram Bot API CDN URL if file_id is available
        file_id = chap_doc.get("file_id")
        bot = bot_getter() if callable(bot_getter) else bot_getter
        if bot and file_id and len(str(file_id)) > 20:
            try:
                tg_file = bot.get_file(file_id)
                if tg_file and tg_file.file_path:
                    import requests
                    req = requests.get(tg_file.file_path, stream=True, timeout=30)
                    if req.status_code == 200:
                        resp = Response(
                            req.iter_content(chunk_size=65536),
                            content_type="application/pdf"
                        )
                        resp.headers["Cache-Control"] = "public, max-age=604800, immutable"
                        resp.headers["Access-Control-Allow-Origin"] = "*"
                        resp.headers["Access-Control-Allow-Headers"] = "Range, Content-Type, Accept"
                        resp.headers["Access-Control-Expose-Headers"] = "Content-Range, Content-Length, Accept-Ranges"
                        return resp
            except Exception as e:
                logger.debug(f"Bot API get_file fallback: {e}")

        return jsonify({
            "success": False,
            "error": "This chapter is available directly in the Telegram channel.",
            "channel_link": direct_post_link
        }), 502

    # -------------------------------------------------------------
    # 🔥 API: Chapter Reactions (🔥 😱 ❤️ 👑)
    # -------------------------------------------------------------
    @app.route("/api/chapter/reactions", methods=["GET"])
    def api_get_chapter_reactions():
        cid_raw = request.args.get("channel_id") or request.args.get("cid")
        ch_raw = request.args.get("chapter") or request.args.get("ch")
        user_id_raw = request.args.get("user_id")

        if not cid_raw or not ch_raw:
            return jsonify({"success": False, "error": "channel_id and chapter are required"}), 400

        try:
            cid = int(cid_raw)
            ch = int(ch_raw)
            user_id = int(user_id_raw) if user_id_raw and user_id_raw.isdigit() else None
        except ValueError:
            return jsonify({"success": False, "error": "Invalid channel_id or chapter format"}), 400

        from database import get_chapter_reactions
        reactions = get_chapter_reactions(cid, ch, user_id)
        return jsonify({"success": True, "reactions": reactions})

    @app.route("/api/chapter/reaction", methods=["POST"])
    def api_toggle_chapter_reaction():
        data = request.get_json(force=True, silent=True) or {}
        cid_raw = data.get("channel_id") or data.get("cid")
        ch_raw = data.get("chapter") or data.get("ch")
        user_id_raw = data.get("user_id")
        reaction = str(data.get("reaction", "")).strip().lower()

        if not cid_raw or not ch_raw or not user_id_raw or not reaction:
            return jsonify({"success": False, "error": "channel_id, chapter, user_id, and reaction are required"}), 400

        try:
            cid = int(cid_raw)
            ch = int(ch_raw)
            user_id = int(user_id_raw)
        except ValueError:
            return jsonify({"success": False, "error": "Invalid ID formats"}), 400

        from database import toggle_chapter_reaction
        reactions = toggle_chapter_reaction(cid, ch, user_id, reaction)
        return jsonify({"success": True, "reactions": reactions})

    # -------------------------------------------------------------
    # 💬 API: Chapter Community Comments, Likes, Edits, & Deletions
    # -------------------------------------------------------------
    @app.route("/api/chapter/comments", methods=["GET"])
    def api_get_chapter_comments():
        cid_raw = request.args.get("channel_id") or request.args.get("cid")
        ch_raw = request.args.get("chapter") or request.args.get("ch")
        user_id_raw = request.args.get("user_id")

        if not cid_raw or not ch_raw:
            return jsonify({"success": False, "error": "channel_id and chapter are required"}), 400

        try:
            cid = int(cid_raw)
            ch = int(ch_raw)
            user_id = int(user_id_raw) if user_id_raw and user_id_raw.isdigit() else None
        except ValueError:
            return jsonify({"success": False, "error": "Invalid format"}), 400

        from database import get_chapter_comments
        comments = get_chapter_comments(cid, ch, user_id)
        return jsonify({"success": True, "count": len(comments), "comments": comments})

    @app.route("/api/chapter/comment", methods=["POST"])
    def api_add_chapter_comment():
        data = request.get_json(force=True, silent=True) or {}
        cid_raw = data.get("channel_id") or data.get("cid")
        ch_raw = data.get("chapter") or data.get("ch")
        user_id_raw = data.get("user_id")
        user_name = str(data.get("user_name", "Reader")).strip()
        user_avatar = data.get("user_avatar")
        text = str(data.get("text", "")).strip()

        if not cid_raw or not ch_raw or not user_id_raw or not text:
            return jsonify({"success": False, "error": "channel_id, chapter, user_id, and text are required"}), 400

        try:
            cid = int(cid_raw)
            ch = int(ch_raw)
            user_id = int(user_id_raw)
        except ValueError:
            return jsonify({"success": False, "error": "Invalid format"}), 400

        from database import add_chapter_comment
        new_comment = add_chapter_comment(cid, ch, user_id, user_name, text, user_avatar=user_avatar)
        if not new_comment:
            return jsonify({"success": False, "error": "Failed to post comment"}), 400

        return jsonify({"success": True, "comment": new_comment})

    @app.route("/api/chapter/comment/edit", methods=["POST"])
    def api_edit_chapter_comment():
        data = request.get_json(force=True, silent=True) or {}
        comment_id = str(data.get("comment_id", "")).strip()
        user_id_raw = data.get("user_id")
        new_text = str(data.get("text", "")).strip()

        if not comment_id or not user_id_raw or not new_text:
            return jsonify({"success": False, "error": "comment_id, user_id, and text are required"}), 400

        try:
            user_id = int(user_id_raw)
        except ValueError:
            return jsonify({"success": False, "error": "Invalid user_id"}), 400

        from database import is_sudo, edit_chapter_comment
        from config import BOT_OWNER_ID
        is_admin = is_sudo(user_id) or user_id == BOT_OWNER_ID
        res = edit_chapter_comment(comment_id, user_id, new_text, is_admin=is_admin)
        return jsonify(res)

    @app.route("/api/chapter/comment/delete", methods=["POST"])
    def api_delete_chapter_comment():
        data = request.get_json(force=True, silent=True) or {}
        comment_id = str(data.get("comment_id", "")).strip()
        user_id_raw = data.get("user_id")

        if not comment_id or not user_id_raw:
            return jsonify({"success": False, "error": "comment_id and user_id are required"}), 400

        try:
            user_id = int(user_id_raw)
        except ValueError:
            return jsonify({"success": False, "error": "Invalid user_id"}), 400

        from database import is_sudo, delete_chapter_comment
        from config import BOT_OWNER_ID
        is_admin = is_sudo(user_id) or user_id == BOT_OWNER_ID
        res = delete_chapter_comment(comment_id, user_id, is_admin=is_admin)
        return jsonify(res)

    @app.route("/api/chapter/comment/like", methods=["POST"])
    def api_like_chapter_comment():
        data = request.get_json(force=True, silent=True) or {}
        comment_id = str(data.get("comment_id", "")).strip()
        user_id_raw = data.get("user_id")

        if not comment_id or not user_id_raw:
            return jsonify({"success": False, "error": "comment_id and user_id are required"}), 400

        try:
            user_id = int(user_id_raw)
        except ValueError:
            return jsonify({"success": False, "error": "Invalid user_id"}), 400

        from database import toggle_comment_like
        res = toggle_comment_like(comment_id, user_id)
        return jsonify(res)

    # -------------------------------------------------------------
    # 👤 API: User Profile Avatar Fetcher from Telegram Bot API
    # -------------------------------------------------------------
    _avatar_cache = {}
    @app.route("/api/user/avatar/<int:user_id>", methods=["GET"])
    def api_get_user_avatar(user_id):
        # 1. Check in-memory avatar cache
        if user_id in _avatar_cache:
            return redirect(_avatar_cache[user_id])

        bot = bot_getter() if callable(bot_getter) else bot_getter
        if bot and user_id:
            try:
                photos = bot.get_user_profile_photos(user_id, limit=1)
                if photos and photos.total_count > 0 and len(photos.photos) > 0:
                    photo_file = photos.photos[0][0]
                    tg_file = bot.get_file(photo_file.file_id)
                    if tg_file and tg_file.file_path:
                        _avatar_cache[user_id] = tg_file.file_path
                        return redirect(tg_file.file_path)
            except Exception as e:
                logger.debug(f"User avatar fetch error for {user_id}: {e}")

        # Fallback to sleek UI avatar with initials
        fallback_url = f"https://api.dicebear.com/7.x/bottts/svg?seed={user_id}&backgroundColor=1e1b4b"
        _avatar_cache[user_id] = fallback_url
        return redirect(fallback_url)


