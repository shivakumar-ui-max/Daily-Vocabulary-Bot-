import os
import datetime
import asyncio
import logging
import threading
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
from pymongo import MongoClient
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
CHAT_ID = os.getenv("CHAT_ID")
APP_URL = os.getenv("APP_URL")
PORT = int(os.environ.get("PORT", 8080))

# MongoDB Connection
client = MongoClient(MONGO_URI)
try:
    client.admin.command('ping')
    logger.info("MongoDB connection successful")
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")

db = client.vocab_bot
words_collection = db.words

app = Flask(__name__)
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

# Commands

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /start from {update.message.chat_id}")
    await update.message.reply_text(
        "🙏 Welcome to Daily Vocabulary Bot!\n"
        "Every day at 8 AM, you'll receive 2 new vocabulary words.\n"
        "Use /history to see past words."
    )

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /history from {update.message.chat_id}")
    messages = []
    for doc in words_collection.find().sort("date", -1).limit(5):
        msg = f"📅 *{doc['date']}*\n\n"
        for i, word in enumerate(doc["words"], 1):
            msg += (
                f"{i}️⃣ *Word*: {word['word']}\n"
                f"*Meaning*: {word['meaning_en']}\n"
                f"*Synonyms*: {', '.join(word['synonyms_en'])}\n"
                f"*Antonyms*: {', '.join(word['antonyms_en'])}\n"
                f"*Examples*:\n- " + "\n- ".join(word['examples_en']) + "\n\n"
            )
            msg += (
                f"{i}️⃣ *Word*: {word['word_te']}\n"
                f"*Meaning*: {word['meaning_te']}\n"
                f"*Synonyms*: {', '.join(word['synonyms_te'])}\n"
                f"*Antonyms*: {', '.join(word['antonyms_te'])}\n"
                f"*Examples*:\n- " + "\n- ".join(word['examples_te']) + "\n\n"
            )
        messages.append(msg)

    await update.message.reply_text("\n\n".join(messages), parse_mode="Markdown")

# Daily Job

async def send_daily_vocab(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Running daily vocabulary job")
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    today_words = words_collection.find_one({"date": today})
    if not today_words:
        logger.info("No words for today")
        return

    msg = "📚 *Today's Vocabulary*\n\n"
    for i, word in enumerate(today_words["words"], 1):
        msg += (
            f"{i}️⃣ *Word*: {word['word']}\n"
            f"*Meaning*: {word['meaning_en']}\n"
            f"*Synonyms*: {', '.join(word['synonyms_en'])}\n"
            f"*Antonyms*: {', '.join(word['antonyms_en'])}\n"
            f"*Examples*:\n- " + "\n- ".join(word['examples_en']) + "\n\n"
        )
        msg += (
            f"{i}️⃣ *Word*: {word['word_te']}\n"
            f"*Meaning*: {word['meaning_te']}\n"
            f"*Synonyms*: {', '.join(word['synonyms_te'])}\n"
            f"*Antonyms*: {', '.join(word['antonyms_te'])}\n"
            f"*Examples*:\n- " + "\n- ".join(word['examples_te']) + "\n\n"
        )

    await context.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")

# Flask Webhook

@app.route("/webhook", methods=["POST"])
def webhook():
    logger.info("Received webhook update")
    try:
        json_data = request.get_json(force=True)
        update = Update.de_json(json_data, telegram_app.bot)
        asyncio.run(telegram_app.process_update(update))
    except Exception as e:
        logger.error(f"Webhook error: {e}")
    return "ok", 200

@app.route("/", methods=["GET"])
def home():
    return "Bot is running!"

# Telegram Bot Main Loop

async def main():
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("history", history))

    telegram_app.job_queue.run_daily(
        send_daily_vocab,
        time=datetime.time(hour=8, minute=0),
        name="daily_vocab",
        job_kwargs={"misfire_grace_time": 300}
    )

    await telegram_app.initialize()
    await telegram_app.bot.set_webhook(f"{APP_URL}/webhook")
    await telegram_app.start()
    logger.info("✅ Bot is ready!")

def run_bot():
    asyncio.run(main())

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT)
