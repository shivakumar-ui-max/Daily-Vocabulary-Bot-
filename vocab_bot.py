import os
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import Update
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

client = MongoClient(MONGO_URI)
db = client.vocab_bot
words_collection = db.words

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🙏 Welcome to Daily Vocabulary Bot!\n"
        "Every day at 8 AM, you will receive 2 new vocabulary words automatically.\n"
        "Use /history to see past words."
    )

async def send_daily_vocab(context: ContextTypes.DEFAULT_TYPE):
    chat_id = os.getenv("CHAT_ID")  # Set your chat id here or store in DB
    today_words = words_collection.find_one({"date": datetime.now().strftime("%Y-%m-%d")})
    if not today_words:
        return  # No words for today yet

    msg = "📚 *Today's Vocabulary*\n\n"
    for i, word in enumerate(today_words["words"], 1):
        msg += f"{i}. *{word['word']}* - {word['meaning']}\n"

    await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    messages = []
    for doc in words_collection.find().sort("date", -1).limit(5):
        words = "\n".join([f"{w['word']} - {w['meaning']}" for w in doc["words"]])
        messages.append(f"📅 {doc['date']}:\n{words}")

    await update.message.reply_text("\n\n".join(messages))

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("history", history))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_vocab, trigger="cron", hour=8, minute=0, args=[app.bot])
    scheduler.start()

    app.run_polling()

if __name__ == "__main__":
    main()
