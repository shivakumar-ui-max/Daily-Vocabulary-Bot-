import os
import datetime
import logging
import pytz
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    Application
)
from pymongo import MongoClient
from dotenv import load_dotenv
from telegram.constants import ParseMode
from telegram.ext import Defaults
from datetime import timedelta

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
history_collection = db.words_history  # For 31-day rolling history

def format_word_message(word, index=None):
    """Format a word into the message template"""
    prefix = f"{index}️⃣ " if index else ""
    return (
        f"{prefix}*Word*: {word.get('English_Word', '')}\n"
        f"*Meaning*: {word.get('English_Meaning', '')}\n"
        f"*Synonyms*: {word.get('English_Synonyms', '')}\n"
        f"*Antonyms*: {word.get('English_Antonyms', '')}\n"
        f"*Examples*:\n- " + "\n- ".join(word.get('English_Examples', '').split(";")) + "\n\n"
        f"{prefix}*పదం*: {word.get('Telugu_Word', '')}\n"
        f"*అర్థం*: {word.get('Telugu_Meaning', '')}\n"
        f"*పర్యాయపదాలు*: {word.get('Telugu_Synonyms', '')}\n"
        f"*విరుద్ధపదాలు*: {word.get('Telugu_Antonyms', '')}\n"
        f"*ఉదాహరణలు*:\n- " + "\n- ".join(word.get('Telugu_Examples', '').split(";")) + "\n"
    )

async def maintain_history(words, now):
    """Maintain 31-day rolling history"""
    try:
        # Add today's words to history
        for word in words:
            history_collection.insert_one({
                **word,
                "date_sent": now,
                "original_id": word["_id"]
            })
        
        # Remove entries older than 31 days
        cutoff = now - timedelta(days=31)
        history_collection.delete_many({"date_sent": {"$lt": cutoff}})
        logger.info(f"History maintained - Added {len(words)}, pruned old entries")
    except Exception as e:
        logger.error(f"History maintenance failed: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 *Vocabulary Bot*\n"
        "• 2 words daily at 8 AM IST\n"
        "• /history - 31-day calendar\n"
        "• /today - Today's words\n"
        "• /testjob - Trigger manually\n\n"
        "Demo Features:\n"
        "- 31-day auto-rotating history\n"
        "- Book-themed formatting\n"
        "- Dual-language support",
        parse_mode="Markdown"
    )

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show 31-day calendar with decorated bilingual entries"""
    try:
        # Get grouped words from history collection
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

        response = "🗓 *31-Day Vocabulary History*\n" \
                  "✦━━━━━━✦❘  📖  ❘✦━━━━━━✦\n\n"
        
        for day in days:
            date_str = day["_id"]
            words = day["words"][:2]  # Limit to 2 words/day
            
            response += f"📅 *{date_str}*\n"
            for word in words:
                # English with sparkle emoji
                response += f"✨ *{word['English_Word']}* - {word['English_Meaning']}\n"
                # Telugu with flower emoji
                response += f"🌸 *{word['Telugu_Word']}* - {word['Telugu_Meaning']}\n"
                response += "⸻⸻⸻\n"  # Thin divider
            
            response += "\n"  # Space between dates

        await update.message.reply_text(
            response, 
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"History error: {e}")
        await update.message.reply_text("Error loading history")

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show today's words in detail"""
    today_start = datetime.datetime.now(pytz.timezone('Asia/Kolkata')).replace(
        hour=0, minute=0, second=0, microsecond=0)
    
    today_words = list(words_collection.find({
        "date_sent": {"$gte": today_start}
    }).limit(2))
    
    if today_words:
        response = "📅 *Today's Words*\n\n"
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
            await context.bot.send_message(
                chat_id=CHAT_ID,
                text="⚠️ No more unsent words!"
            )
            return

        # Build message with book-themed separator
        message = "📚 *Daily Vocabulary*\n\n"
        for i, word in enumerate(words, 1):
            message += format_word_message(word, i)
            if i < len(words):
                message += "\n📖━━━━━━✧❘  📚  ❘✧━━━━━━📖\n\n"
            
            # Mark as sent in main collection
            words_collection.update_one(
                {"_id": word["_id"]},
                {"$set": {
                    "sent": True,
                    "date_sent": now
                }}
            )

        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            parse_mode="Markdown"
        )
        
        # Update history collection
        await maintain_history(words, now)
        
    except Exception as e:
        logger.error(f"Daily send failed: {e}")
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text="❌ Error sending words"
        )

async def test_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually trigger today's words"""
    await update.message.reply_text("🔄 Sending today's words...")
    await send_daily_vocab(context)

async def post_init(application: Application):
    """Initialize webhook and send startup message"""
    await application.bot.set_webhook(
        url=f"{APP_URL}/{BOT_TOKEN}",
        allowed_updates=Update.ALL_TYPES
    )
    
    try:
        await application.bot.send_message(
            chat_id=CHAT_ID,
            text=f"🤖 Bot restarted at {datetime.datetime.now(pytz.timezone('Asia/Kolkata'))}\n"
                 "Next words at 8 AM IST"
        )
    except Exception as e:
        logger.error(f"Startup message failed: {e}")

def main():
    application = ApplicationBuilder() \
        .token(BOT_TOKEN) \
        .defaults(Defaults(parse_mode=ParseMode.MARKDOWN)) \
        .post_init(post_init) \
        .build()

    # Command handlers
    handlers = [
        CommandHandler("start", start),
        CommandHandler("history", history),
        CommandHandler("today", today),
        CommandHandler("testjob", test_job)
    ]
    for handler in handlers:
        application.add_handler(handler)

    # Schedule daily job
    ist = pytz.timezone('Asia/Kolkata')
    application.job_queue.run_daily(
        send_daily_vocab,
        time=datetime.time(8, 0, tzinfo=ist),
        name="daily_vocab"
    )

    # Start bot
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"{APP_URL}/{BOT_TOKEN}",
        url_path=BOT_TOKEN,
        drop_pending_updates=True
    )

if __name__ == "__main__":
    main()