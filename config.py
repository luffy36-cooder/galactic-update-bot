import os
import logging
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://luffy:4jBiQfxN9uDOpo6a@cluster0.wc9tlbk.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")


def _load_bot_token() -> str:
    """Dynamically loads the bot token from MongoDB Vault without exposing it in source code."""
    try:
        from pymongo import MongoClient
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=4000)
        db = client["manga_bot"]
        doc = db["bot_settings"].find_one({"key": "bot_token"})
        if doc and doc.get("value"):
            return str(doc["value"]).strip()
    except Exception as e:
        logging.warning(f"Failed to fetch BOT_TOKEN from DB Vault: {e}")
    return os.getenv("BOT_TOKEN", "").strip()


BOT_TOKEN = _load_bot_token()
API_ID = int(os.getenv("API_ID", "26630701"))
API_HASH = os.getenv("API_HASH", "7e4079ed188ead6f00d411a6e91b9455")
UPDATE_CHANNEL_ID = int(os.getenv("UPDATE_CHANNEL_ID", "-1002887680811"))
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", "6600689593"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "-1002182636182"))
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://galactic-update-bot-zq8c.onrender.com").rstrip("/")
