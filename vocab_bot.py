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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🙏 Welcome to Daily Vocabulary Bot!\n"
        "• Get 2 words daily at 8 AM IST\n"
        "• /history - Show 31-day calendar (2 words/day)\n"
        "• /today - Today's words\n"
        "• /testjob - Manually send today's words"
    )

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show 31-day vocabulary calendar with 2 words per day"""
    cutoff_date = datetime.datetime.now(pytz.timezone('Asia/Kolkata')) - timedelta(days=31)
    
    # Get up to 2 words per day
    pipeline = [
        {"$match": {"date_sent": {"$gte": cutoff_date}}},
        {"$sort": {"date_sent": -1}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$date_sent"}},
            "words": {"$push": "$$ROOT"},
            "count": {"$sum": 1}
        }},
        {"$project": {
            "words": {"$slice": ["$words", 2]},  # Limit to 2 words per day
            "date": "$_id"
        }},
        {"$sort": {"date": -1}},
        {"$limit": 31}  # 31 days
    ]
    
    daily_words = list(words_collection.aggregate(pipeline))
    
    if not daily_words:
        await update.message.reply_text("No vocabulary history available!")
        return

    # Build calendar message
    calendar_msg = "🗓 *31-Day Vocabulary Calendar*\n(2 words per day)\n\n"
    for entry in daily_words:
        date_str = entry["date"]
        words = entry["words"]
        calendar_msg += f"📅 *{date_str}*\n"
        for word in words:
            calendar_msg += f"✨ {word['English_Word']} - {word['English_Meaning']}\n"
        calendar_msg += "\n"

    await update.message.reply_text(calendar_msg, parse_mode="Markdown")

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
        
        # Get 2 oldest unsent words
        words = list(words_collection.find({"sent": {"$exists": False}}).limit(2))
        
        if not words:
            logger.warning("No new words available")
            await context.bot.send_message(
                chat_id=CHAT_ID,
                text="ℹ️ No new vocabulary words available today!"
            )
            return

        # Send words with numbering
        message = "📚 *Daily Vocabulary (2 Words)*\n\n"
        for i, word in enumerate(words, 1):
            message += format_word_message(word, i)
            
            # Mark as sent with current timestamp
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
        
    except Exception as e:
        logger.error(f"Error sending daily vocab: {e}")
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text="❌ Error sending today's words. Please check logs."
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
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .defaults(Defaults(parse_mode=ParseMode.MARKDOWN))
        .post_init(post_init)
        .build()
    )

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("history", history))
    application.add_handler(CommandHandler("today", today))
    application.add_handler(CommandHandler("testjob", test_job))

    # Schedule daily job at 8 AM IST
    ist = pytz.timezone('Asia/Kolkata')
    application.job_queue.run_daily(
        send_daily_vocab,
        time=datetime.time(8, 0, tzinfo=ist),
        name="daily_vocab"
    )

    # Start the bot
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"{APP_URL}/{BOT_TOKEN}",
        url_path=BOT_TOKEN,
        drop_pending_updates=True
    )

if __name__ == "__main__":
    main()