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

# Set up logging
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
PORT = int(os.environ.get("PORT", 8080))  # Default to 8080 for Render

# MongoDB connection
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /start command from chat_id: {update.message.chat_id}")
    try:
        await update.message.reply_text(
            "🙏 Welcome to Daily Vocabulary Bot!\n"
            "Every day at 8 AM, you will receive 2 new vocabulary words automatically.\n"
            "Use /history to see past words."
        )
    except Exception as e:
        logger.error(f"Error in /start command: {e}")

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /history command from chat_id: {update.message.chat_id}")
    try:
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
    except Exception as e:
        logger.error(f"Error in /history command: {e}")
        await update.message.reply_text("Error retrieving history. Please try again later.")

async def send_daily_vocab(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Running daily vocabulary job")
    try:
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        today_words = words_collection.find_one({"date": today})
        if not today_words:
            logger.info("No words found for today")
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
    except Exception as e:
        logger.error(f"Error in daily vocab job: {e}")

@app.route(f'/{BOT_TOKEN}', methods=["POST"])
def webhook():
    logger.info("Received webhook update")
    try:
        json_data = request.get_json(force=True)
        if not json_data:
            logger.warning("No JSON data received in webhook")
            return "ok", 200
        update = Update.de_json(json_data, telegram_app.bot)
        if update:
            telegram_app.process_update(update)
            logger.info("Update processed successfully")
        else:
            logger.warning("Received invalid update")
        return "ok", 200
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return "ok", 200  # Return 200 to avoid Telegram retrying

@app.route("/", methods=["GET"])
def health():
    return "Bot is running!"

async def main():
    try:
        telegram_app.add_handler(CommandHandler("start", start))
        telegram_app.add_handler(CommandHandler("history", history))

        telegram_app.job_queue.run_daily(
            send_daily_vocab,
            time=datetime.time(hour=8, minute=0),
            name="daily_vocab",
            job_kwargs={"misfire_grace_time": 300}
        )

        await telegram_app.initialize()
        logger.info(f"Setting webhook: {APP_URL}/{BOT_TOKEN}")
        await telegram_app.bot.set_webhook(f"{APP_URL}/{BOT_TOKEN}")
        await telegram_app.start()
        logger.info("✅ Bot is ready!")
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise

def run_bot():
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Error running bot: {e}")

if __name__ == "__main__":
    # Start the bot in a separate thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    # Run Flask app
    app.run(host="0.0.0.0", port=PORT)