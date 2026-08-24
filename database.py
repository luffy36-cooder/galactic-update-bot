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


# ==========================================
# ⚡ In-Memory High-Speed Caching Layer
# ==========================================
_manga_cache = None
_manga_cache_time = 0
MANGA_CACHE_TTL = 60  # Refresh cache every 60 seconds or on mutation

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
        logger.info("✅ Database indexes initialized successfully.")
    except Exception as e:
        logger.warning(f"⚠️ Index initialization notice: {e}")


def _invalidate_manga_cache():
    global _manga_cache, _manga_cache_time
    _manga_cache = None
    _manga_cache_time = 0


def _get_cached_manga_list():
    global _manga_cache, _manga_cache_time
    now = time.time()
    if _manga_cache is None or (now - _manga_cache_time) > MANGA_CACHE_TTL:
        _manga_cache = list(manga_col.find())
        _manga_cache_time = now
    return _manga_cache


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
    return manga_col.find_one({"channel_id": channel_id}) or {}


def get_manga_by_id(channel_id):
    return manga_col.find_one({"channel_id": channel_id})


def update_manga_image(channel_id, image_file_id):
    manga_col.update_one({"channel_id": channel_id}, {"$set": {"image": image_file_id}})
    _invalidate_manga_cache()


# ==========================================
# 🔍 Manga Search (In-Memory RapidFuzz: <1ms)
# ==========================================
def search_manga_by_name(query: str, limit: int = 5, cutoff: int = 55):
    if not query or not query.strip():
        return []

    clean_query = query.strip()
    all_manga = _get_cached_manga_list()
    if not all_manga:
        return []

    # 🥇 Step 1: Exact case-insensitive match
    exact = next((m for m in all_manga if m.get("name", "").lower() == clean_query.lower()), None)
    if exact:
        return [exact]

    # 🥈 Step 2: In-memory fuzzy search
    names = [m.get("name", "") for m in all_manga if m.get("name")]
    if not names:
        return []

    matches = process.extract(clean_query, names, scorer=fuzz.WRatio, limit=limit)
    valid_matches = [m for m in matches if m[1] >= cutoff]

    if not valid_matches:
        return []

    matched_names = [m[0] for m in valid_matches]
    results = [m for m in all_manga if m.get("name") in matched_names]
    results.sort(key=lambda x: matched_names.index(x.get("name", "")))
    return results


# ==========================================
# 🛠 Admin Tools
# ==========================================
def remove_manga_by_name(name: str):
    escaped_name = re.escape(name.strip())
    res = manga_col.delete_one({"name": {"$regex": f"^{escaped_name}$", "$options": "i"}})
    _invalidate_manga_cache()
    return res.deleted_count > 0


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

    bookmarks_col.update_one(
        {"user_id": user_id, "manga": canonical_name},
        {"$set": {
            "manga": canonical_name,
            "chapter": str(chapter),
            "channel_id": channel_id,
            "channel_link": channel_link,
            "updated_at": datetime.utcnow()
        }},
        upsert=True
    )
    increment_user_achievement(user_id, "bookmarks")
    return True


def get_user_bookmarks(user_id: int):
    return list(bookmarks_col.find({"user_id": user_id}, {"_id": 0}))


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
    increment_user_achievement(user_id, "ratings")
    return True


def get_manga_rating_summary(channel_id: int, user_id: int = None):
    """Returns average rating, total review count, and current user's rating."""
    pipeline = [
        {"$match": {"channel_id": channel_id}},
        {"$group": {
            "_id": "$channel_id",
            "avg_rating": {"$avg": "$rating"},
            "total_ratings": {"$sum": 1}
        }}
    ]
    res = list(ratings_col.aggregate(pipeline))
    avg_rating = round(res[0]["avg_rating"], 1) if res else 0.0
    total_ratings = res[0]["total_ratings"] if res else 0

    user_rating = None
    if user_id:
        doc = ratings_col.find_one({"channel_id": channel_id, "user_id": user_id}, {"rating": 1})
        if doc:
            user_rating = doc.get("rating")

    return {
        "avg_rating": avg_rating,
        "total_ratings": total_ratings,
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
