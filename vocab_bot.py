import os
import datetime
import logging
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    Application
)
from pymongo import MongoClient
from dotenv import load_dotenv
from telegram.constants import ParseMode
from telegram.ext import Defaults
from datetime import timedelta
from gtts import gTTS

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
PORT = int(os.environ.get("PORT", 10000))

# MongoDB Connection
client = MongoClient(MONGO_URI)
try:
    client.admin.command('ping')
    logger.info("MongoDB connection successful")
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")

db = client.vocab_bot
words_collection = db.words
history_collection = db.words_history

def format_word_message(word, index=None):
    prefix = f"{index}⃣ " if index else ""
    return (
        f"{prefix}*Word*: {word.get('English_Word', '')} \[🔊](pronounce_{word.get('_id')})\n"
        f"*Meaning*: {word.get('English_Meaning', '')}\n"
        f"*Synonyms*: {word.get('English_Synonyms', '')}\n"
        f"*Antonyms*: {word.get('English_Antonyms', '')}\n"
        f"*Examples*:\n- " + "\n- ".join(word.get('English_Examples', '').split(";")) + "\n\n"
        f"{prefix}*పదం*: {word.get('Telugu_Word', '')} \[🔊](pronounce_te_{word.get('_id')})\n"
        f"*అర్థం*: {word.get('Telugu_Meaning', '')}\n"
        f"*పర్యాయపదాలు*: {word.get('Telugu_Synonyms', '')}\n"
        f"*విరుద్ధపదాలు*: {word.get('Telugu_Antonyms', '')}\n"
        f"*ఉదాహరణలు*:\n- " + "\n- ".join(word.get('Telugu_Examples', '').split(";")) + "\n"
    )

async def maintain_history(words, now):
    try:
        for word in words:
            history_collection.insert_one({
                **word,
                "date_sent": now,
                "original_id": word["_id"]
            })
        cutoff = now - timedelta(days=31)
        history_collection.delete_many({"date_sent": {"$lt": cutoff}})
        logger.info(f"History maintained - Added {len(words)}, pruned old entries")
    except Exception as e:
        logger.error(f"History maintenance failed: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "\ud83d\udcda *Vocabulary Bot*\n"
        "\u2022 2 words daily at 8 AM IST\n"
        "\u2022 /history - 31-day calendar\n"
        "\u2022 /today - Today's words\n"
        "\u2022 /testjob - Trigger manually",
        parse_mode="Markdown"
    )

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        pipeline = [
            {"$sort": {"date_sent": -1}},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$date_sent"}},
                "words": {"$push": "$$ROOT"},
            }},
            {"$sort": {"_id": -1}},
            {"$limit": 31}
        ]
        days = list(history_collection.aggregate(pipeline))

        if not days:
            await update.message.reply_text("No history available yet!")
            return

        response = "\ud83d\uddd3 *31-Day Vocabulary History*\n\u2726\u2501\u2501\u2501\u2501\u2726\u2757\ufe0f  \ud83d\udcd6  \u2757\ufe0f\u2726\u2501\u2501\u2501\u2501\u2726\n\n"
        for day in days:
            date_str = day["_id"]
            words = day["words"][:2]
            response += f"\ud83d\udcc5 *{date_str}*\n"
            for word in words:
                response += f"\u2728 *{word['English_Word']}* - {word['English_Meaning']}\n"
                response += f"\ud83c\udf38 *{word['Telugu_Word']}* - {word['Telugu_Meaning']}\n"
                response += "\u23bb\u23bb\u23bb\n"
            response += "\n"

        await update.message.reply_text(response, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"History error: {e}")
        await update.message.reply_text("Error loading history")

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today_start = datetime.datetime.now(pytz.timezone('Asia/Kolkata')).replace(
        hour=0, minute=0, second=0, microsecond=0)
    today_words = list(words_collection.find({"date_sent": {"$gte": today_start}}).limit(2))

    if today_words:
        response = "\ud83d\udcc5 *Today's Words*\n\n"
        for i, word in enumerate(today_words, 1):
            response += format_word_message(word, i) + "\n"
        await update.message.reply_text(response, parse_mode="Markdown")
    else:
        await update.message.reply_text("No words sent today yet!")

async def send_daily_vocab(context: ContextTypes.DEFAULT_TYPE):
    try:
        now = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
        words = list(words_collection.find({"sent": {"$exists": False}}).limit(2))

        if not words:
            logger.warning("No words available")
            await context.bot.send_message(chat_id=CHAT_ID, text="\u26a0\ufe0f No more unsent words!")
            return

        message = "\ud83d\udcda *Daily Vocabulary*\n\n"
        for i, word in enumerate(words, 1):
            message += format_word_message(word, i)
            if i < len(words):
                message += "\n\ud83d\udcd6\u2501\u2501\u2501\u2501\u2727\u2757\ufe0f  \ud83d\udcda  \u2757\ufe0f\u2727\u2501\u2501\u2501\u2501\ud83d\udcd6\n\n"
            words_collection.update_one(
                {"_id": word["_id"]},
                {"$set": {"sent": True, "date_sent": now}}
            )

        await context.bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")
        await maintain_history(words, now)

    except Exception as e:
        logger.error(f"Daily send failed: {e}")
        await context.bot.send_message(chat_id=CHAT_ID, text="\u274c Error sending words")

async def test_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("\ud83d\udd04 Sending today's words...")
    await send_daily_vocab(context)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    lang = 'en'
    word_id = data
    if data.startswith('pronounce_te_'):
        lang = 'te'
        word_id = data.replace('pronounce_te_', '')
    elif data.startswith('pronounce_'):
        word_id = data.replace('pronounce_', '')

    word_doc = words_collection.find_one({"_id": int(word_id)})
    if word_doc:
        text = word_doc['English_Word'] if lang == 'en' else word_doc['Telugu_Word']
        tts = gTTS(text=text, lang=lang)
        tts.save("voice.mp3")
        with open("voice.mp3", "rb") as audio:
            await query.message.reply_audio(audio)

async def post_init(application: Application):
    await application.bot.set_webhook(url=f"{APP_URL}/{BOT_TOKEN}", allowed_updates=Update.ALL_TYPES)
    try:
        await application.bot.send_message(
            chat_id=CHAT_ID,
            text=f"\ud83e\udd16 Bot restarted at {datetime.datetime.now(pytz.timezone('Asia/Kolkata'))}\nNext words at 8 AM IST"
        )
    except Exception as e:
        logger.error(f"Startup message failed: {e}")

def main():
    application = ApplicationBuilder() \
        .token(BOT_TOKEN) \
        .defaults(Defaults(parse_mode=ParseMode.MARKDOWN)) \
        .post_init(post_init) \
        .build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("history", history))
    application.add_handler(CommandHandler("today", today))
    application.add_handler(CommandHandler("testjob", test_job))
    application.add_handler(CallbackQueryHandler(button_callback))

    ist = pytz.timezone('Asia/Kolkata')
    application.job_queue.run_daily(send_daily_vocab, time=datetime.time(8, 0, tzinfo=ist), name="daily_vocab")

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"{APP_URL}/{BOT_TOKEN}",
        url_path=BOT_TOKEN,
        drop_pending_updates=True
    )

if __name__ == "__main__":
    main()
