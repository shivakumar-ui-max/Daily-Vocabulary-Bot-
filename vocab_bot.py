import os
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import Update
from pymongo import MongoClient
from dotenv import load_dotenv
import datetime

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
CHAT_ID = os.getenv("CHAT_ID")
APP_URL = os.getenv("APP_URL")
PORT = int(os.environ["PORT"])
WEBHOOK_URL = "https://daily-vocabulary-bot.onrender.com/vocab-secret-123"  # Replace with your webhook path

client = MongoClient(MONGO_URI)
db = client.vocab_bot
words_collection = db.words

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🙏 Welcome to Daily Vocabulary Bot!\n"
        "Every day at 8 AM, you will receive 2 new vocabulary words automatically.\n"
        "Use /history to see past words."
    )

# /history command
async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    messages = []
    for doc in words_collection.find().sort("date", -1).limit(5):
        words = "\n".join([f"{w['word']} - {w['meaning']}" for w in doc["words"]])
        messages.append(f"📅 {doc['date']}:\n{words}")

    await update.message.reply_text("\n\n".join(messages))

# Daily vocab sender
async def send_daily_vocab(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    today_words = words_collection.find_one({"date": today})
    if not today_words:
        return

    msg = "📚 *Today's Vocabulary*\n\n"
    for i, word in enumerate(today_words["words"], 1):
        msg += f"{i}. *{word['word']}* - {word['meaning']}\n"

    await context.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")

# Main app
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("history", history))

    # Schedule daily vocab at 8:00 AM
    app.job_queue.run_daily(
        send_daily_vocab,
        time=datetime.time(hour=8, minute=0),
    )

    # Webhook start
    app.run_webhook(
    listen="0.0.0.0",
    port=PORT,
    webhook_url=f"{APP_URL}/{BOT_TOKEN}"
    )

if __name__ == "__main__":
    main()
