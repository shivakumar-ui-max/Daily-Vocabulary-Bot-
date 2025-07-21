import os
import datetime
import logging
import requests
import pytz
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

# MongoDB Connection
client = MongoClient(MONGO_URI)
db = client.vocab_bot
words_collection = db.words

# Flask App
app = Flask(__name__)

# Telegram App
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

# Commands

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /start from {update.effective_chat.id}")
    await update.message.reply_text(
        "🙏 Welcome to Daily Vocabulary Bot!\n"
        "Every day at 8 AM, you'll receive 2 new vocabulary words.\n"
        "Use /history to see past words."
    )

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /history from {update.effective_chat.id}")
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

# Flask Routes

@app.route("/", methods=["GET"])
def home():
    return "OK", 200

@app.route("/webhook", methods=["POST"])
async def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return "OK", 200

# Setup Telegram Handlers

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("history", history))

# Schedule Daily Job
ist = pytz.timezone("Asia/Kolkata")
telegram_app.job_queue.run_daily(
    send_daily_vocab,
    time=datetime.time(hour=8, minute=0, tzinfo=ist),
    name="daily_vocab"
)

# Webhook Setup

with telegram_app:
    webhook_url = f"{APP_URL}/webhook"
    res = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}")
    if res.status_code == 200:
        logger.info("Webhook set successfully")
    else:
        logger.error(f"Webhook error: {res.text}")

    telegram_app.initialize()
    telegram_app.start()
    telegram_app.updater.start_polling()  # Required for job queue
