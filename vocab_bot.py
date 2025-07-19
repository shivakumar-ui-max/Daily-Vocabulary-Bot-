import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

client = MongoClient(MONGO_URI)
db = client["daily_vocab"]
collection = db["words"]

async def send_daily_word(application):
    chat_ids = set()  # Replace this with actual chat_ids if stored in DB
    cursor = collection.aggregate([{"$sample": {"size": 2}}])
    words = list(cursor)

    message = "📚 **Today's Vocabulary**\n"
    for word in words:
        message += f"\n**{word['english_word']}** - {word['meaning_en']}\n_{word['meaning_te']}_"

    for chat_id in chat_ids:
        await application.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🙏 Welcome to Daily Vocabulary Bot!\n"
        "Every day at 8 AM, you will receive 2 new vocabulary words automatically.\n"
        "Use /history to see past words."
    )

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor = collection.find().sort("_id", -1).limit(10)
    words = list(cursor)

    message = "**Last 10 Words:**\n"
    for word in words:
        message += f"\n**{word['english_word']}** - {word['meaning_en']}\n"

    await update.message.reply_text(message, parse_mode="Markdown")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("history", history))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_word, "cron", hour=8, minute=0, args=[app])
    scheduler.start()

    app.run_polling()

if __name__ == "__main__":
    main()
