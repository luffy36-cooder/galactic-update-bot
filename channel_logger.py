from telegram import Update, ChatMemberUpdated
from telegram.ext import CallbackContext
from database import channels_col

# 🌐 Triggered when bot's chat status changes
def chat_member_update(update: Update, context: CallbackContext):
    chat = update.effective_chat
    member_update: ChatMemberUpdated = update.my_chat_member

    bot_id = context.bot.id
    old_status = member_update.old_chat_member.status
    new_status = member_update.new_chat_member.status

    # 🛡️ Only care if bot is added or promoted
    if new_status in ["administrator", "creator"]:
        if chat.type not in ["channel", "supergroup", "group"]:
            return  # Ignore private or unknown types

        channels_col.update_one(
            {"channel_id": chat.id},
            {"$set": {
                "channel_id": chat.id,
                "name": chat.title or "Unnamed Chat",
                "type": chat.type,
            }},
            upsert=True
        )
        print(f"[LOG] ✅ Bot is ADMIN in: {chat.title} ({chat.id})")

    # ❌ If bot removed or demoted
    elif new_status in ["left", "kicked", "restricted", "member"] and old_status in ["administrator", "creator"]:
        result = channels_col.delete_one({"channel_id": chat.id})
        print(f"[LOG] ❌ Bot REMOVED from: {chat.title} ({chat.id}) — Cleaned: {result.deleted_count}")
