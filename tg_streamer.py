import os
import queue
import threading
import asyncio
import logging
from telethon import TelegramClient
from telethon.sessions import MemorySession
from config import API_ID, API_HASH, BOT_TOKEN
from database import save_chapter_file, manga_col
from channel_handler import extract_chapter_number

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache", "pdfs")
SESSION_DIR = os.path.join(os.path.dirname(__file__), "cache", "session")
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(SESSION_DIR, exist_ok=True)
SESSION_FILE = os.path.join(SESSION_DIR, "galactic_streamer")


class MTProtoStreamer:
    def __init__(self):
        self.loop = None
        self.client = None
        self.ready_event = threading.Event()
        self._download_locks = {}
        self._lock_mutex = threading.Lock()
        self.thread = threading.Thread(target=self._worker, daemon=True, name="MTProtoStreamerWorker")
        self.thread.start()
        self.ready_event.wait(timeout=10)

    def _worker(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.client = TelegramClient(SESSION_FILE, API_ID, API_HASH, loop=self.loop)

        async def _connect():
            try:
                await self.client.connect()
                if not await self.client.is_user_authorized():
                    await self.client.start(bot_token=BOT_TOKEN)
                logger.info("🚀 MTProto Telethon Streamer successfully authenticated with Telegram!")
            except Exception as e:
                logger.warning(f"MTProto authentication notice: {e}")
            finally:
                self.ready_event.set()

        self.loop.run_until_complete(_connect())
        self.loop.run_forever()

    def get_or_download_pdf(self, channel_id: int, msg_id: int) -> str:
        """Downloads and caches the PDF on disk with thread-safe de-duplication, returning file path."""
        os.makedirs(CACHE_DIR, exist_ok=True)
        cache_path = os.path.join(CACHE_DIR, f"{channel_id}_{msg_id}.pdf")
        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 5000:
            return cache_path

        lock_key = f"{channel_id}_{msg_id}"
        with self._lock_mutex:
            if lock_key not in self._download_locks:
                self._download_locks[lock_key] = threading.Event()
                is_initiator = True
            else:
                is_initiator = False
                wait_event = self._download_locks[lock_key]

        if not is_initiator:
            wait_event.wait(timeout=45)
            if os.path.exists(cache_path) and os.path.getsize(cache_path) > 5000:
                return cache_path
            return None

        try:
            async def _download():
                try:
                    msg = await self.client.get_messages(channel_id, ids=msg_id)
                    if msg and msg.document:
                        temp_path = f"{cache_path}.tmp"
                        await self.client.download_media(msg.document, file=temp_path)
                        if os.path.exists(temp_path) and os.path.getsize(temp_path) > 5000:
                            if os.path.exists(cache_path):
                                os.remove(cache_path)
                            os.rename(temp_path, cache_path)
                    else:
                        logger.warning(f"No document found on msg_id {msg_id} in channel {channel_id}")
                except Exception as e:
                    logger.error(f"Download error on {channel_id}:{msg_id} -> {e}")

            if self.loop and self.loop.is_running():
                fut = asyncio.run_coroutine_threadsafe(_download(), self.loop)
                fut.result(timeout=45)
        finally:
            with self._lock_mutex:
                ev = self._download_locks.pop(lock_key, None)
                if ev:
                    ev.set()

        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 5000:
            return cache_path
        return None

    def stream_pdf(self, channel_id: int, msg_id: int):
        """Generates stream chunks of the PDF with zero file size limits!"""
        q = queue.Queue(maxsize=16)

        async def _download():
            try:
                msg = await self.client.get_messages(channel_id, ids=msg_id)
                if msg and msg.document:
                    async for chunk in self.client.iter_download(msg.document, chunk_size=256 * 1024):
                        q.put(chunk)
                else:
                    logger.warning(f"No document on message ID {msg_id} in channel {channel_id}")
            except Exception as e:
                logger.error(f"Error in MTProto iter_download: {e}")
            finally:
                q.put(None)

        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(_download(), self.loop)

        while True:
            chunk = q.get()
            if chunk is None:
                break
            yield chunk

    def scan_channel_batch(self, channel_id: int, start_id: int = 1, end_id: int = 400) -> int:
        """Batch-fetches up to 400 messages in seconds and indexes all PDF chapters into DB!"""
        msg_ids = list(range(start_id, end_id + 1))
        indexed_count = 0
        highest_chapter = 0

        async def _scan():
            nonlocal indexed_count, highest_chapter
            for i in range(0, len(msg_ids), 100):
                batch = msg_ids[i:i + 100]
                try:
                    msgs = await self.client.get_messages(channel_id, ids=batch)
                    for m in msgs:
                        if m and m.file and m.file.name and m.file.name.lower().endswith(".pdf"):
                            ch = extract_chapter_number(m.file.name)
                            if ch is not None:
                                save_chapter_file(channel_id, ch, str(m.id), m.file.name, m.id)
                                indexed_count += 1
                                if ch > highest_chapter:
                                    highest_chapter = ch
                except Exception as e:
                    logger.error(f"Batch scan error on channel {channel_id}: {e}")

        if self.loop and self.loop.is_running():
            fut = asyncio.run_coroutine_threadsafe(_scan(), self.loop)
            fut.result(timeout=60)

        if highest_chapter > 0:
            manga_col.update_one({"channel_id": channel_id}, {"$set": {"total_chapters": highest_chapter}})

        return indexed_count


# Global singleton instance
_streamer = None

def get_streamer() -> MTProtoStreamer:
    global _streamer
    if _streamer is None:
        _streamer = MTProtoStreamer()
    return _streamer

