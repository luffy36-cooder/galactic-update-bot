import time
from telegram import Update
from telegram.ext import CallbackContext

def ping_cmd(update: Update, context: CallbackContext):
    start = time.time()
    msg =  update.message.reply_text("Pinging...")
    end = time.time()
    ping_ms = int((end - start) * 1000)
    msg.edit_text(f"🏓 Pong! `{ping_ms}ms`", parse_mode="Markdown")
