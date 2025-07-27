import os
import datetime
import logging
import pytz
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
from pymongo import MongoClient
from dotenv import load_dotenv
from telegram.constants import ParseMode
from telegram.ext import Defaults

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
PORT = int(os.environ.get("PORT", 10000))  # Default to Render's port

# MongoDB Connection
client = MongoClient(MONGO_URI)
try:
    client.admin.command('ping')
    logger.info("MongoDB connection successful")
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")

db = client.vocab_bot
words_collection = db.words

# Commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /start from {update.effective_chat.id}")
    await update.message.reply_text(
        "🙏 Welcome to Daily Vocabulary Bot!\n"
        "Every day at 8 AM, you'll receive new vocabulary words.\n"
        "Use /history to see recent words."
    )

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /history from {update.effective_chat.id}")
    messages = []
    for i, word in enumerate(words_collection.find().sort("_id", -1).limit(5), 1):
        msg = (
            f"{i}️⃣ *Word*: {word.get('English_Word', '')}\n"
            f"*Meaning*: {word.get('English_Meaning', '')}\n"
            f"*Synonyms*: {word.get('English_Synonyms', '')}\n"
            f"*Antonyms*: {word.get('English_Antonyms', '')}\n"
            f"*Examples*:\n- " + "\n- ".join(word.get('English_Examples', '').split(";")) + "\n\n"
            f"{i}️⃣ *పదం*: {word.get('Telugu_Word', '')}\n"
            f"*అర్థం*: {word.get('Telugu_Meaning', '')}\n"
            f"*పర్యాయపదాలు*: {word.get('Telugu_Synonyms', '')}\n"
            f"*విరుద్ధపదాలు*: {word.get('Telugu_Antonyms', '')}\n"
            f"*ఉదాహరణలు*:\n- " + "\n- ".join(word.get('Telugu_Examples', '').split(";")) + "\n\n"
        )
        messages.append(msg)

    for chunk in messages:
        await update.message.reply_text(chunk, parse_mode="Markdown")

async def send_daily_vocab(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Running daily vocabulary job")
    msg = "📚 *Today's Vocabulary*\n\n"
    full_text = ""

    for i, word in enumerate(words_collection.find(), 1):
        entry = (
            f"{i}️⃣ *Word*: {word.get('English_Word', '')}\n"
            f"*Meaning*: {word.get('English_Meaning', '')}\n"
            f"*Synonyms*: {word.get('English_Synonyms', '')}\n"
            f"*Antonyms*: {word.get('English_Antonyms', '')}\n"
            f"*Examples*:\n- " + "\n- ".join(word.get('English_Examples', '').split(";")) + "\n\n"
            f"{i}️⃣ *పదం*: {word.get('Telugu_Word', '')}\n"
            f"*అర్థం*: {word.get('Telugu_Meaning', '')}\n"
            f"*పర్యాయపదాలు*: {word.get('Telugu_Synonyms', '')}\n"
            f"*విరుద్ధపదాలు*: {word.get('Telugu_Antonyms', '')}\n"
            f"*ఉదాహరణలు*:\n- " + "\n- ".join(word.get('Telugu_Examples', '').split(";")) + "\n\n"
        )

        if len(full_text) + len(entry) > 4000:
            await context.bot.send_message(chat_id=CHAT_ID, text=msg + full_text, parse_mode="Markdown")
            full_text = ""

        full_text += entry

    if full_text:
        await context.bot.send_message(chat_id=CHAT_ID, text=msg + full_text, parse_mode="Markdown")

async def main():
    defaults = Defaults(parse_mode=ParseMode.MARKDOWN)
    logger.info("Creating application")
    try:
        application = ApplicationBuilder().token(BOT_TOKEN).defaults(defaults).build()
        logger.info("Application created")
    except Exception as e:
        logger.error(f"Failed to build application: {e}")
        raise

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("history", history))

    webhook_url = f"{APP_URL}/{BOT_TOKEN}"
    logger.info(f"Setting webhook URL: {webhook_url}")
    try:
        await application.bot.set_webhook(url=webhook_url)
        logger.info("Webhook set successfully")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
        raise

    logger.info("Scheduling daily vocabulary job")
    try:
        application.job_queue.run_daily(
            send_daily_vocab,
            time=datetime.time(hour=8, minute=0, tzinfo=pytz.timezone("Asia/Kolkata")),
            name="daily_vocab"
        )
    except Exception as e:
        logger.error(f"Failed to schedule job: {e}")
        raise

    logger.info("Starting webhook")
    try:
        await application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=webhook_url
        )
    except Exception as e:
        logger.error(f"Webhook setup failed: {e}")
        raise

if __name__ == "__main__":
    # Fix for Python 3.10+ event loop handling
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(main())
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        loop.close()