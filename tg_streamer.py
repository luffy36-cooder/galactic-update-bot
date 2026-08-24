import queue
import threading
import asyncio
import logging
from telethon import TelegramClient
from config import API_ID, API_HASH, BOT_TOKEN
from database import save_chapter_file, manga_col
from channel_handler import extract_chapter_number

logger = logging.getLogger(__name__)


class MTProtoStreamer:
    def __init__(self):
        self.loop = None
        self.client = None
        self.ready_event = threading.Event()
        self.thread = threading.Thread(target=self._worker, daemon=True, name="MTProtoStreamerWorker")
        self.thread.start()
        self.ready_event.wait(timeout=15)

    def _worker(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.client = TelegramClient("galactic_streamer", API_ID, API_HASH, loop=self.loop)

        async def _connect():
            await self.client.start(bot_token=BOT_TOKEN)
            logger.info("🚀 MTProto Telethon Streamer successfully authenticated with Telegram!")
            self.ready_event.set()

        self.loop.run_until_complete(_connect())
        self.loop.run_forever()

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
            # Split into chunks of 100 to avoid hitting batch limits
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
