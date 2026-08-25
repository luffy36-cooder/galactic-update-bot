import re
import time
import logging
from datetime import datetime
from pymongo import MongoClient, ASCENDING, DESCENDING
from config import MONGO_URI
from rapidfuzz import process, fuzz

logger = logging.getLogger(__name__)

# ✅ Connect to DB
client = MongoClient(MONGO_URI)
db = client["manga_bot"]

# 📁 Collections
channels_col = db["channels"]
manga_col = db["manga_info"]
modes_col = db["group_modes"]
bookmarks_col = db["user_bookmarks"]
achievements_col = db["user_achievements"]
read_log_col = db["read_log"]
manga_status_col = db["user_manga_status"]
posted_chapter_col = db["posted_chapters"]
sudo_col = db["sudo_users"]
request_col = db["manga_requests"]
broadcast_log_col = db["broadcast_log"]
ratings_col = db["manga_ratings"]
subscriptions_col = db["manga_subscriptions"]
chapter_files_col = db["chapter_files"]
chapter_reactions_col = db["chapter_reactions"]
chapter_comments_col = db["chapter_comments"]


# ==========================================
# ⚡ In-Memory High-Speed Caching Layer
# ==========================================
_manga_cache = None
_manga_by_id_cache = {}
_manga_cache_time = 0
MANGA_CACHE_TTL = 60  # Refresh cache every 60 seconds or on mutation

_ratings_cache = None
_ratings_cache_time = 0
RATINGS_CACHE_TTL = 60

_sudo_cache = None
_modes_cache = {}


def init_db_indexes():
    """Ensure essential indexes exist for lightning-fast queries."""
    try:
        channels_col.create_index([("channel_id", ASCENDING)], unique=True)
        manga_col.create_index([("channel_id", ASCENDING)], unique=True, sparse=True)
        manga_col.create_index([("name", ASCENDING)])
        modes_col.create_index([("chat_id", ASCENDING)], unique=True)
        bookmarks_col.create_index([("user_id", ASCENDING), ("manga", ASCENDING)])
        achievements_col.create_index([("user_id", ASCENDING)], unique=True)
        read_log_col.create_index([("user_id", ASCENDING), ("chapter", ASCENDING)])
        read_log_col.create_index([("deleted", ASCENDING)])
        read_log_col.create_index([("manga_id", ASCENDING)])
        manga_status_col.create_index([("user_id", ASCENDING), ("channel_id", ASCENDING)])
        posted_chapter_col.create_index([("channel_id", ASCENDING)], unique=True)
        sudo_col.create_index([("user_id", ASCENDING)], unique=True)
        request_col.create_index([("status", ASCENDING)])
        broadcast_log_col.create_index([("original_msg_id", ASCENDING)])
        ratings_col.create_index([("channel_id", ASCENDING), ("user_id", ASCENDING)], unique=True)
        subscriptions_col.create_index([("channel_id", ASCENDING), ("user_id", ASCENDING)], unique=True)
        subscriptions_col.create_index([("user_id", ASCENDING)])
        chapter_files_col.create_index([("channel_id", ASCENDING), ("chapter", ASCENDING)], unique=True)
        chapter_files_col.create_index([("channel_id", ASCENDING)])
        logger.info("✅ Database indexes initialized successfully.")
    except Exception as e:
        logger.warning(f"⚠️ Index initialization notice: {e}")


def _invalidate_manga_cache():
    global _manga_cache, _manga_by_id_cache, _manga_cache_time
    _manga_cache = None
    _manga_by_id_cache = {}
    _manga_cache_time = 0


def _get_cached_manga_list():
    global _manga_cache, _manga_by_id_cache, _manga_cache_time
    now = time.time()
    if _manga_cache is None or (now - _manga_cache_time) > MANGA_CACHE_TTL:
        _manga_cache = list(manga_col.find().sort("name", 1))
        _manga_by_id_cache = {m["channel_id"]: m for m in _manga_cache if "channel_id" in m}
        _manga_cache_time = now
    return _manga_cache


def get_all_manga_cached():
    """Returns in-memory cached list of all manga."""
    return _get_cached_manga_list()


def _invalidate_ratings_cache():
    global _ratings_cache, _ratings_cache_time
    _ratings_cache = None
    _ratings_cache_time = 0


def get_all_ratings_cached():
    """Returns in-memory cached ratings summary for all manga."""
    global _ratings_cache, _ratings_cache_time
    now = time.time()
    if _ratings_cache is None or (now - _ratings_cache_time) > RATINGS_CACHE_TTL:
        try:
            pipeline = [
                {"$group": {
                    "_id": "$channel_id",
                    "avg_rating": {"$avg": "$rating"},
                    "total_ratings": {"$sum": 1}
                }}
            ]
            _ratings_cache = {
                doc["_id"]: {
                    "avg_rating": round(float(doc["avg_rating"]), 1),
                    "total_ratings": int(doc["total_ratings"])
                }
                for doc in ratings_col.aggregate(pipeline)
            }
        except Exception:
            _ratings_cache = {}
        _ratings_cache_time = now
    return _ratings_cache


# Initialize indexes on load
init_db_indexes()


# ==========================================
# 🔐 Sudo System (Cached)
# ==========================================
def _load_sudo_cache():
    global _sudo_cache
    _sudo_cache = {doc["user_id"] for doc in sudo_col.find({}, {"user_id": 1}) if "user_id" in doc}
    return _sudo_cache


def is_sudo(user_id: int) -> bool:
    global _sudo_cache
    if _sudo_cache is None:
        _load_sudo_cache()
    return user_id in _sudo_cache


def add_sudo(user_id: int):
    global _sudo_cache
    sudo_col.update_one({"user_id": user_id}, {"$set": {"user_id": user_id}}, upsert=True)
    if _sudo_cache is not None:
        _sudo_cache.add(user_id)


def remove_sudo(user_id: int):
    global _sudo_cache
    sudo_col.delete_one({"user_id": user_id})
    if _sudo_cache is not None:
        _sudo_cache.discard(user_id)


def get_all_sudo():
    global _sudo_cache
    if _sudo_cache is None:
        _load_sudo_cache()
    return list(_sudo_cache)


# ==========================================
# 📌 Channel Management
# ==========================================
def add_channel(channel_id, name=None, link=None, image=None):
    data = {
        "channel_id": channel_id,
        "name": name or "Unknown",
        "link": link or "",
        "image": image
    }
    channels_col.update_one({"channel_id": channel_id}, {"$set": data}, upsert=True)


def get_all_channels():
    return [doc["channel_id"] for doc in channels_col.find({}, {"channel_id": 1}) if "channel_id" in doc]


def get_last_msg_id(channel_id):
    doc = channels_col.find_one({"channel_id": channel_id}, {"last_msg": 1})
    return doc.get("last_msg", 0) if doc else 0


def set_last_msg_id(channel_id, chapter):
    channels_col.update_one({"channel_id": channel_id}, {"$set": {"last_msg": chapter}})


# ==========================================
# 📚 Manga Info (Cached)
# ==========================================
def set_manga_info(channel_id, name, link, image=None):
    manga_col.update_one(
        {"channel_id": channel_id},
        {"$set": {
            "channel_id": channel_id,
            "name": name,
            "channel_link": link,
            "image": image
        }},
        upsert=True
    )
    _invalidate_manga_cache()


def get_manga_info(channel_id):
    m = get_manga_by_id(channel_id)
    return m or {}


def get_manga_by_id(channel_id):
    if _manga_by_id_cache and channel_id in _manga_by_id_cache:
        return _manga_by_id_cache[channel_id]
    _get_cached_manga_list()
    if _manga_by_id_cache and channel_id in _manga_by_id_cache:
        return _manga_by_id_cache[channel_id]
    return manga_col.find_one({"channel_id": channel_id})


def update_manga_image(channel_id, image_file_id):
    manga_col.update_one({"channel_id": channel_id}, {"$set": {"image": image_file_id}})
    _invalidate_manga_cache()


# ==========================================
# 🔍 Manga Search (In-Memory RapidFuzz: <1ms)
# ==========================================
def search_manga_by_name(query: str, limit: int = 6, cutoff: int = 50):
    if not query or not query.strip():
        return []

    clean_query = query.strip()
    clean_lower = clean_query.lower()
    all_manga = _get_cached_manga_list()
    if not all_manga:
        return []

    # 🥇 Step 1: Exact case-insensitive match
    exact = next((m for m in all_manga if m.get("name", "").lower() == clean_lower), None)
    if exact:
        return [exact]

    # 🥈 Step 2: Substring matching (e.g. "solo", "demon", "dragon", "villain")
    substring_matches = [m for m in all_manga if clean_lower in m.get("name", "").lower()]

    # 🥉 Step 3: Fuzzy token-set matching
    names = [m.get("name", "") for m in all_manga if m.get("name")]
    fuzzy_res = process.extract(clean_query, names, scorer=fuzz.token_set_ratio, limit=limit)
    fuzzy_names = [f[0] for f in fuzzy_res if f[1] >= cutoff]

    combined_names = []
    for m in substring_matches:
        n = m.get("name")
        if n and n not in combined_names:
            combined_names.append(n)

    for n in fuzzy_names:
        if n and n not in combined_names:
            combined_names.append(n)

    if not combined_names:
        return []

    results = [m for m in all_manga if m.get("name") in combined_names]
    results.sort(key=lambda x: combined_names.index(x.get("name", "")))
    return results[:limit]


# ==========================================
# 🛠 Admin Tools
# ==========================================
def remove_manga_by_name(name: str):
    escaped_name = re.escape(name.strip())
    m = manga_col.find_one({"name": {"$regex": f"^{escaped_name}$", "$options": "i"}})
    if m and m.get("channel_id"):
        return delete_manga_completely(m["channel_id"])
    res = manga_col.delete_one({"name": {"$regex": f"^{escaped_name}$", "$options": "i"}})
    _invalidate_manga_cache()
    return res.deleted_count > 0


def delete_manga_completely(channel_id: int):
    """Permanently deletes manga and all associated chapters, ratings, reactions, and comments from MongoDB."""
    m_res = manga_col.delete_one({"channel_id": channel_id})
    try:
        chapter_files_col.delete_many({"channel_id": channel_id})
        ratings_col.delete_many({"channel_id": channel_id})
        chapter_reactions_col.delete_many({"channel_id": channel_id})
        chapter_comments_col.delete_many({"channel_id": channel_id})
    except Exception:
        pass
    _invalidate_manga_cache()
    return m_res.deleted_count > 0


def list_all_manga():
    return list(manga_col.find({}, {"_id": 0, "name": 1, "channel_link": 1, "channel_id": 1}))


def edit_manga_link_or_name(name: str, new_name=None, new_link=None):
    update_data = {}
    if new_name:
        update_data["name"] = new_name
    if new_link:
        update_data["channel_link"] = new_link
    if not update_data:
        return None

    escaped_name = re.escape(name.strip())
    res = manga_col.update_one(
        {"name": {"$regex": f"^{escaped_name}$", "$options": "i"}},
        {"$set": update_data}
    )
    _invalidate_manga_cache()
    return res


# ==========================================
# 🎛️ Group Modes (Cached)
# ==========================================
def set_group_mode(chat_id: int, mode: str):
    modes_col.update_one({"chat_id": chat_id}, {"$set": {"mode": mode}}, upsert=True)
    _modes_cache[chat_id] = mode


def get_group_mode(chat_id: int):
    if chat_id in _modes_cache:
        return _modes_cache[chat_id]
    doc = modes_col.find_one({"chat_id": chat_id}, {"mode": 1})
    mode = doc["mode"] if doc and "mode" in doc else "text"
    _modes_cache[chat_id] = mode
    return mode


# ==========================================
# 📌 Bookmarks
# ==========================================
def save_user_bookmark(user_id: int, manga_name: str, chapter: int):
    manga_list = search_manga_by_name(manga_name)
    if not manga_list:
        return False

    manga = manga_list[0]
    canonical_name = manga.get("name", manga_name)
    channel_link = manga.get("channel_link", "")
    channel_id = manga.get("channel_id")

    # 🎯 Auto-resolve exact chapter post link from chapter_files_col!
    direct_post_link = channel_link
    if channel_id and str(chapter).isdigit():
        chap_doc = chapter_files_col.find_one({"channel_id": channel_id, "chapter": int(chapter)})
        if chap_doc and chap_doc.get("msg_id"):
            from channel_handler import build_post_link
            direct_post_link = build_post_link(channel_id, chap_doc["msg_id"], channel_link)

    bookmarks_col.update_one(
        {"user_id": user_id, "manga": canonical_name},
        {"$set": {
            "manga": canonical_name,
            "chapter": str(chapter),
            "channel_id": channel_id,
            "channel_link": channel_link,
            "post_link": direct_post_link,
            "updated_at": datetime.utcnow()
        }},
        upsert=True
    )
    increment_user_achievement(user_id, "bookmarks")
    return True


def get_user_bookmarks(user_id: int):
    bms = list(bookmarks_col.find({"user_id": user_id}, {"_id": 0}))
    for b in bms:
        if not b.get("post_link") and b.get("channel_id") and str(b.get("chapter", "")).isdigit():
            cid = b.get("channel_id")
            ch = int(b.get("chapter"))
            c_link = b.get("channel_link", "")
            chap_doc = chapter_files_col.find_one({"channel_id": cid, "chapter": ch})
            if chap_doc and chap_doc.get("msg_id"):
                from channel_handler import build_post_link
                b["post_link"] = build_post_link(cid, chap_doc["msg_id"], c_link)
    return bms


def remove_bookmark(user_id: int, manga_name: str):
    escaped_name = re.escape(manga_name.strip())
    return bookmarks_col.delete_one({
        "user_id": user_id,
        "manga": {"$regex": f"^{escaped_name}$", "$options": "i"}
    })


def clear_user_bookmarks(user_id: int):
    result = bookmarks_col.delete_many({"user_id": user_id})
    return result.deleted_count > 0


# ==========================================
# 🏆 Achievements & Reading Logs
# ==========================================
def increment_user_achievement(user_id: int, field: str):
    achievements_col.update_one(
        {"user_id": user_id},
        {"$inc": {field: 1}},
        upsert=True
    )


def get_user_achievements(user_id: int):
    return achievements_col.find_one({"user_id": user_id}) or {}


def mark_chapter_as_read(user_id: int, channel_id: int, chapter_number: int = 0) -> bool:
    key = f"{channel_id}_{chapter_number}"
    existing = read_log_col.find_one({"user_id": user_id, "chapter": key})

    if existing:
        if existing.get("deleted", False):
            read_log_col.update_one(
                {"_id": existing["_id"]},
                {"$set": {"deleted": False}}
            )
            increment_user_achievement(user_id, "read")
            return True
        return False

    read_log_col.insert_one({
        "user_id": user_id,
        "chapter": key,
        "manga_id": channel_id,
        "timestamp": datetime.utcnow(),
        "deleted": False
    })
    increment_user_achievement(user_id, "read")
    return True


# ==========================================
# 🧠 Status Tags
# ==========================================
def update_manga_status(user_id: int, channel_id: int, status: str, add=True):
    if add:
        manga_status_col.update_one(
            {"user_id": user_id, "channel_id": channel_id},
            {"$addToSet": {"status": status}},
            upsert=True
        )
    else:
        manga_status_col.update_one(
            {"user_id": user_id, "channel_id": channel_id},
            {"$pull": {"status": status}}
        )


def get_user_manga_lists(user_id: int):
    results = list(manga_status_col.find({"user_id": user_id}))
    lists = {"read": [], "completed": [], "favorite": [], "dropped": [], "hold": []}
    for item in results:
        for stat in item.get("status", []):
            if stat in lists:
                lists[stat].append(item["channel_id"])
    return lists


def get_user_manga_status(user_id: int, channel_id: int):
    doc = manga_status_col.find_one({"user_id": user_id, "channel_id": channel_id}, {"status": 1})
    return doc.get("status", []) if doc else []


# ==========================================
# 🎖️ Badges & Profiles
# ==========================================
def get_user_badges(user_id: int):
    a = get_user_achievements(user_id)
    badges = []
    if a.get("bookmarks", 0) >= 1:
        badges.append("📚")
    r = a.get("read", 0)
    if r >= 20:
        badges.append("🌟🌟🌟🌟")
    elif r >= 15:
        badges.append("🌟🌟🌟")
    elif r >= 10:
        badges.append("🌟🌟")
    elif r >= 1:
        badges.append("🌟")
    return badges


def get_user_profile(user_id: int):
    bookmarks = bookmarks_col.count_documents({"user_id": user_id})
    read = get_user_achievements(user_id).get("read", 0)
    return {"bookmarks": bookmarks, "read_count": read}


# ==========================================
# 🧠 Smart Chapter Tracking
# ==========================================
def was_chapter_posted(channel_id, chapter):
    data = posted_chapter_col.find_one({"channel_id": channel_id}, {"chapters": 1})
    return bool(data and chapter in data.get("chapters", []))


def mark_chapter_posted(channel_id, chapter):
    posted_chapter_col.update_one(
        {"channel_id": channel_id},
        {"$addToSet": {"chapters": chapter}},
        upsert=True
    )
    # Auto-update total_chapters in manga_info
    try:
        chap_num = int(chapter)
        manga = manga_col.find_one({"channel_id": channel_id}, {"total_chapters": 1})
        if manga:
            current_total = manga.get("total_chapters", 0)
            if chap_num > current_total:
                manga_col.update_one(
                    {"channel_id": channel_id},
                    {"$set": {"total_chapters": chap_num}}
                )
                _invalidate_manga_cache()
    except (ValueError, TypeError):
        pass


def unmark_chapter_posted(channel_id, chapter):
    posted_chapter_col.update_one(
        {"channel_id": channel_id},
        {"$pull": {"chapters": chapter}}
    )


# ==========================================
# ⭐ Community Ratings & Reviews
# ==========================================
def save_manga_rating(user_id: int, user_name: str, channel_id: int, rating: int, review: str = None):
    """Saves or updates a user rating (1-5) and optional review."""
    rating = max(1, min(5, int(rating)))
    data = {
        "channel_id": channel_id,
        "user_id": user_id,
        "user_name": user_name or "Anonymous",
        "rating": rating,
        "review": review.strip() if review else None,
        "updated_at": datetime.utcnow()
    }
    ratings_col.update_one(
        {"channel_id": channel_id, "user_id": user_id},
        {"$set": data},
        upsert=True
    )
    _invalidate_ratings_cache()
    increment_user_achievement(user_id, "ratings")
    return True


def get_manga_rating_summary(channel_id: int, user_id: int = None):
    """Returns average rating, total review count, and current user's rating."""
    all_rat = get_all_ratings_cached()
    summary = all_rat.get(channel_id, {"avg_rating": 0.0, "total_ratings": 0})
    user_rating = None
    if user_id:
        doc = ratings_col.find_one({"channel_id": channel_id, "user_id": user_id}, {"rating": 1})
        if doc:
            user_rating = doc.get("rating")

    return {
        "avg_rating": summary.get("avg_rating", 0.0),
        "total_ratings": summary.get("total_ratings", 0),
        "user_rating": user_rating
    }


def get_manga_reviews(channel_id: int, limit: int = 5):
    """Fetches the latest reviews for a manga."""
    raw_reviews = list(ratings_col.find(
        {"channel_id": channel_id, "review": {"$ne": None}},
        {"_id": 0, "user_name": 1, "rating": 1, "review": 1, "updated_at": 1}
    ).sort("updated_at", DESCENDING).limit(limit))
    for r in raw_reviews:
        if isinstance(r.get("updated_at"), datetime):
            r["updated_at"] = r["updated_at"].strftime("%b %d, %Y")
    return raw_reviews


def get_top_rated_manga(limit: int = 10):
    """Returns top-rated manga by average rating with at least 1 rating."""
    pipeline = [
        {"$group": {
            "_id": "$channel_id",
            "avg_rating": {"$avg": "$rating"},
            "total_ratings": {"$sum": 1}
        }},
        {"$sort": {"avg_rating": -1, "total_ratings": -1}},
        {"$limit": limit}
    ]
    top_entries = list(ratings_col.aggregate(pipeline))
    results = []
    for entry in top_entries:
        cid = entry["_id"]
        manga = get_manga_by_id(cid)
        if manga:
            results.append({
                "channel_id": cid,
                "name": manga.get("name", "Unknown"),
                "channel_link": manga.get("channel_link") or f"https://t.me/c/{str(cid)[4:]}/1",
                "avg_rating": round(entry["avg_rating"], 1),
                "total_ratings": entry["total_ratings"],
                "image": manga.get("image")
            })
    return results


# ==========================================
# 🔔 Auto New Chapter Subscriptions
# ==========================================
def subscribe_manga(user_id: int, channel_id: int) -> bool:
    """Subscribes a user to direct new chapter DM alerts."""
    subscriptions_col.update_one(
        {"channel_id": channel_id, "user_id": user_id},
        {"$set": {"channel_id": channel_id, "user_id": user_id, "created_at": datetime.utcnow()}},
        upsert=True
    )
    return True


def unsubscribe_manga(user_id: int, channel_id: int) -> bool:
    """Unsubscribes a user from new chapter alerts."""
    res = subscriptions_col.delete_one({"channel_id": channel_id, "user_id": user_id})
    return res.deleted_count > 0


def is_user_subscribed(user_id: int, channel_id: int) -> bool:
    return bool(subscriptions_col.find_one({"channel_id": channel_id, "user_id": user_id}))


def get_user_subscriptions(user_id: int):
    """Returns list of channel IDs a user is subscribed to."""
    return [doc["channel_id"] for doc in subscriptions_col.find({"user_id": user_id}, {"channel_id": 1})]


def get_manga_subscribers(channel_id: int) -> list[int]:
    """Returns unique list of user IDs who subscribed or favorited this manga."""
    sub_uids = {doc["user_id"] for doc in subscriptions_col.find({"channel_id": channel_id}, {"user_id": 1})}

    # Also include users who marked this manga as favorite
    fav_uids = {
        doc["user_id"] for doc in manga_status_col.find(
            {"channel_id": channel_id, "status": "favorite"},
            {"user_id": 1}
        )
    }
    return list(sub_uids | fav_uids)


# ==========================================
# 📖 In-App Web Reader Chapter Storage
# ==========================================
def save_chapter_file(channel_id: int, chapter: int, file_id: str, file_name: str = None, msg_id: int = 0):
    """Indexes a chapter PDF file_id for online webtoon/manga reading."""
    data = {
        "channel_id": channel_id,
        "chapter": int(chapter),
        "file_id": file_id,
        "file_name": file_name,
        "msg_id": msg_id,
        "updated_at": datetime.utcnow()
    }
    chapter_files_col.update_one(
        {"channel_id": channel_id, "chapter": int(chapter)},
        {"$set": data},
        upsert=True
    )
    return True


def get_chapter_file(channel_id: int, chapter: int):
    """Retrieves file_id and info for a specific chapter."""
    return chapter_files_col.find_one({"channel_id": channel_id, "chapter": int(chapter)})


def get_manga_chapter_list(channel_id: int):
    """Returns sorted list of available chapters for a manga."""
    # First check chapter_files_col
    files = list(chapter_files_col.find({"channel_id": channel_id}, {"chapter": 1, "_id": 0}))
    if files:
        chaps = sorted({f["chapter"] for f in files})
        return chaps

    # Fallback to posted_chapters_col
    posted = posted_chapter_col.find_one({"channel_id": channel_id})
    if posted and posted.get("chapters"):
        return sorted([int(c) for c in posted["chapters"] if str(c).isdigit()])

    # Fallback to total_chapters count
    manga = get_manga_by_id(channel_id)
    if manga and manga.get("total_chapters"):
        return list(range(1, manga["total_chapters"] + 1))

    return [1]


def auto_sync_all_chapters():
    """Automatically scans posted_chapters and bookmarks to sync total_chapters for all manga."""
    updated_count = 0
    all_manga = list(manga_col.find())

    for m in all_manga:
        cid = m.get("channel_id")
        if not cid:
            continue

        highest_chap = m.get("total_chapters", 0) or 0

        # Check posted_chapters collection
        posted_doc = posted_chapter_col.find_one({"channel_id": cid})
        if posted_doc and posted_doc.get("chapters"):
            for c in posted_doc["chapters"]:
                try:
                    c_int = int(c)
                    if c_int > highest_chap:
                        highest_chap = c_int
                except (ValueError, TypeError):
                    pass

        # Check chapter_files_col
        ch_files = list(chapter_files_col.find({"channel_id": cid}))
        for cf in ch_files:
            c_int = cf.get("chapter")
            if c_int and isinstance(c_int, int) and c_int > highest_chap:
                highest_chap = c_int

        # Check bookmarks
        name = m.get("name", "")
        if name:
            bm_docs = list(bookmarks_col.find({"$or": [{"channel_id": cid}, {"manga": name}]}))
            for b in bm_docs:
                try:
                    c_int = int(b.get("chapter", 0))
                    if c_int > highest_chap:
                        highest_chap = c_int
                except (ValueError, TypeError):
                    pass

        if highest_chap > 0 and highest_chap != m.get("total_chapters"):
            manga_col.update_one(
                {"channel_id": cid},
                {"$set": {"total_chapters": highest_chap}}
            )
            updated_count += 1

    if updated_count > 0:
        _invalidate_manga_cache()
        logger.info(f"✅ Auto-synced total_chapters for {updated_count} manga titles in MongoDB!")

    return updated_count


# =========================================================
# 🔥 Chapter Reactions System (🔥 😱 ❤️ 👑 😂 😭 😡 👎)
# =========================================================
VALID_REACTIONS = {"fire", "shock", "heart", "crown", "laugh", "cry", "angry", "dislike"}

def get_chapter_reactions(channel_id: int, chapter: int, user_id: int = None) -> dict:
    """Returns reaction counts and the current user's reaction."""
    counts = {
        "fire": 0,
        "shock": 0,
        "heart": 0,
        "crown": 0,
        "laugh": 0,
        "cry": 0,
        "angry": 0,
        "dislike": 0,
        "total": 0,
        "user_reaction": None
    }
    try:
        pipeline = [
            {"$match": {"channel_id": int(channel_id), "chapter": int(chapter)}},
            {"$group": {"_id": "$reaction", "count": {"$sum": 1}}}
        ]
        for item in chapter_reactions_col.aggregate(pipeline):
            r_name = item["_id"]
            if r_name in counts:
                counts[r_name] = item["count"]
                counts["total"] += item["count"]

        if user_id:
            user_doc = chapter_reactions_col.find_one({
                "channel_id": int(channel_id),
                "chapter": int(chapter),
                "user_id": int(user_id)
            })
            if user_doc:
                counts["user_reaction"] = user_doc.get("reaction")
    except Exception as e:
        logger.error(f"Error fetching chapter reactions: {e}")

    return counts


def toggle_chapter_reaction(channel_id: int, chapter: int, user_id: int, reaction: str) -> dict:
    """Toggles or changes a user's reaction for a chapter."""
    if reaction not in VALID_REACTIONS:
        return get_chapter_reactions(channel_id, chapter, user_id)

    try:
        existing = chapter_reactions_col.find_one({
            "channel_id": int(channel_id),
            "chapter": int(chapter),
            "user_id": int(user_id)
        })

        if existing and existing.get("reaction") == reaction:
            # Tap same reaction again -> Remove it (toggle off)
            chapter_reactions_col.delete_one({"_id": existing["_id"]})
        else:
            # Insert or switch reaction
            chapter_reactions_col.update_one(
                {"channel_id": int(channel_id), "chapter": int(chapter), "user_id": int(user_id)},
                {"$set": {"reaction": reaction, "updated_at": time.time()}},
                upsert=True
            )
    except Exception as e:
        logger.error(f"Error toggling chapter reaction: {e}")

    return get_chapter_reactions(channel_id, chapter, user_id)


# =========================================================
# 💬 Chapter Community Comments System (with Edit, Delete & Avatar)
# =========================================================
def get_chapter_comments(channel_id: int, chapter: int, user_id: int = None, limit: int = 50) -> list:
    """Fetches formatted comments for a specific chapter."""
    comments = []
    try:
        cursor = chapter_comments_col.find({
            "channel_id": int(channel_id),
            "chapter": int(chapter)
        }).sort("created_at", -1).limit(limit)

        for doc in cursor:
            likes_list = doc.get("likes", [])
            is_liked = bool(user_id and user_id in likes_list)
            comments.append({
                "id": str(doc["_id"]),
                "user_id": doc.get("user_id"),
                "user_name": doc.get("user_name", "Anonymous Reader"),
                "user_avatar": doc.get("user_avatar") or f"/api/user/avatar/{doc.get('user_id')}",
                "text": doc.get("text", ""),
                "created_at": doc.get("created_at", time.time()),
                "edited": doc.get("edited", False),
                "likes_count": len(likes_list),
                "is_liked": is_liked
            })
    except Exception as e:
        logger.error(f"Error fetching chapter comments: {e}")

    return comments


def add_chapter_comment(channel_id: int, chapter: int, user_id: int, user_name: str, text: str, user_avatar: str = None) -> dict:
    """Adds a new comment to a chapter."""
    clean_text = text.strip()[:600]
    if not clean_text:
        return None

    clean_name = (user_name or "Reader").strip()[:50]
    now = time.time()

    doc = {
        "channel_id": int(channel_id),
        "chapter": int(chapter),
        "user_id": int(user_id),
        "user_name": clean_name,
        "user_avatar": user_avatar or f"/api/user/avatar/{user_id}",
        "text": clean_text,
        "created_at": now,
        "edited": False,
        "likes": []
    }

    try:
        res = chapter_comments_col.insert_one(doc)
        return {
            "id": str(res.inserted_id),
            "user_id": int(user_id),
            "user_name": clean_name,
            "user_avatar": doc["user_avatar"],
            "text": clean_text,
            "created_at": now,
            "edited": False,
            "likes_count": 0,
            "is_liked": False
        }
    except Exception as e:
        logger.error(f"Error adding chapter comment: {e}")
        return None


def edit_chapter_comment(comment_id_str: str, user_id: int, new_text: str, is_admin: bool = False) -> dict:
    """Edits a comment text if user is author or admin."""
    from bson.objectid import ObjectId
    clean_text = new_text.strip()[:600]
    if not clean_text:
        return {"success": False, "error": "Comment cannot be empty"}

    try:
        obj_id = ObjectId(comment_id_str)
        doc = chapter_comments_col.find_one({"_id": obj_id})
        if not doc:
            return {"success": False, "error": "Comment not found"}

        if doc.get("user_id") != int(user_id) and not is_admin:
            return {"success": False, "error": "Unauthorized to edit this comment"}

        chapter_comments_col.update_one(
            {"_id": obj_id},
            {"$set": {"text": clean_text, "edited": True, "edited_at": time.time()}}
        )
        return {"success": True, "text": clean_text}
    except Exception as e:
        logger.error(f"Error editing comment: {e}")
        return {"success": False, "error": str(e)}


def delete_chapter_comment(comment_id_str: str, user_id: int, is_admin: bool = False) -> dict:
    """Deletes a comment if user is author or admin."""
    from bson.objectid import ObjectId
    try:
        obj_id = ObjectId(comment_id_str)
        doc = chapter_comments_col.find_one({"_id": obj_id})
        if not doc:
            return {"success": False, "error": "Comment not found"}

        if doc.get("user_id") != int(user_id) and not is_admin:
            return {"success": False, "error": "Unauthorized to delete this comment"}

        chapter_comments_col.delete_one({"_id": obj_id})
        return {"success": True}
    except Exception as e:
        logger.error(f"Error deleting comment: {e}")
        return {"success": False, "error": str(e)}


def toggle_comment_like(comment_id_str: str, user_id: int) -> dict:
    """Toggles like on a comment."""
    from bson.objectid import ObjectId
    try:
        obj_id = ObjectId(comment_id_str)
        doc = chapter_comments_col.find_one({"_id": obj_id})
        if not doc:
            return {"success": False, "error": "Comment not found"}

        likes_list = doc.get("likes", [])
        if user_id in likes_list:
            chapter_comments_col.update_one({"_id": obj_id}, {"$pull": {"likes": int(user_id)}})
            is_liked = False
            new_count = max(0, len(likes_list) - 1)
        else:
            chapter_comments_col.update_one({"_id": obj_id}, {"$addToSet": {"likes": int(user_id)}})
            is_liked = True
            new_count = len(likes_list) + 1

        return {"success": True, "likes_count": new_count, "is_liked": is_liked}
    except Exception as e:
        logger.error(f"Error toggling comment like: {e}")
        return {"success": False, "error": str(e)}

