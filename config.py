import os
from dotenv import load_dotenv

load_dotenv()

_env_token = os.getenv("BOT_TOKEN", "")
if not _env_token or "AAGPWuctdrTPe0WS" in _env_token or "AAGuFy9LubvOMG0SKgWVsbb" in _env_token:
    BOT_TOKEN = "7225497293:AAFBaCtHW_oHjt_HQ1_ELM2eUqD0SoWDdNU"
else:
    BOT_TOKEN = _env_token
API_ID = int(os.getenv("API_ID", "26630701"))
API_HASH = os.getenv("API_HASH", "7e4079ed188ead6f00d411a6e91b9455")
UPDATE_CHANNEL_ID = int(os.getenv("UPDATE_CHANNEL_ID", "-1002887680811"))
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://luffy:4jBiQfxN9uDOpo6a@cluster0.wc9tlbk.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", "6600689593"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "-1002182636182"))
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://galactic-update-bot-zq8c.onrender.com").rstrip("/")
