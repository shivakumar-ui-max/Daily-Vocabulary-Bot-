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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /start from {update.effective_chat.id}")
    await update.message.reply_text(
        "🙏 Welcome to Daily Vocabulary Bot!\n"
        "Every day at 8 AM IST, you'll receive new vocabulary words.\n"
        "Use /history to see recent words.\n"
        "Use /testjob to manually trigger today's words."
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
    try:
        logger.info(f"Running daily vocabulary job at {datetime.datetime.now(pytz.timezone('Asia/Kolkata'))}")
        msg = "📚 *Today's Vocabulary*\n\n"
        
        # Get today's word (you'll need to implement logic to select one new word per day)
        word = words_collection.find_one({"sent": {"$exists": False}})  # Example query
        
        if not word:
            logger.warning("No new words found in database")
            return

        entry = (
            f"1️⃣ *Word*: {word.get('English_Word', '')}\n"
            f"*Meaning*: {word.get('English_Meaning', '')}\n"
            f"*Synonyms*: {word.get('English_Synonyms', '')}\n"
            f"*Antonyms*: {word.get('English_Antonyms', '')}\n"
            f"*Examples*:\n- " + "\n- ".join(word.get('English_Examples', '').split(";")) + "\n\n"
            f"1️⃣ *పదం*: {word.get('Telugu_Word', '')}\n"
            f"*అర్థం*: {word.get('Telugu_Meaning', '')}\n"
            f"*పర్యాయపదాలు*: {word.get('Telugu_Synonyms', '')}\n"
            f"*విరుద్ధపదాలు*: {word.get('Telugu_Antonyms', '')}\n"
            f"*ఉదాహరణలు*:\n- " + "\n- ".join(word.get('Telugu_Examples', '').split(";")) + "\n\n"
        )

        await context.bot.send_message(chat_id=CHAT_ID, text=msg + entry, parse_mode="Markdown")
        
        # Mark word as sent
        words_collection.update_one({"_id": word["_id"]}, {"$set": {"sent": True}})
        
    except Exception as e:
        logger.error(f"Error in send_daily_vocab: {e}", exc_info=True)

async def test_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manual trigger for testing"""
    await update.message.reply_text("🔄 Manually triggering daily vocab...")
    await send_daily_vocab(context)
    await update.message.reply_text("✅ Done!")

async def post_init(application: Application) -> None:
    """Notification when bot starts"""
    await application.bot.set_webhook(
        url=f"{APP_URL}/{BOT_TOKEN}",
        allowed_updates=Update.ALL_TYPES
    )
    logger.info("Webhook setup complete")
    
    # Send startup notification
    try:
        await application.bot.send_message(
            chat_id=CHAT_ID,
            text=f"🤖 Bot restarted at {datetime.datetime.now(pytz.timezone('Asia/Kolkata'))}"
        )
    except Exception as e:
        logger.error(f"Couldn't send startup message: {e}")

def main():
    """Run the bot with proper webhook configuration"""
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .defaults(Defaults(parse_mode=ParseMode.MARKDOWN))
        .post_init(post_init)  # Add post-init handler
        .build()
    )

    # Register commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("history", history))
    application.add_handler(CommandHandler("testjob", test_job))

    # Schedule daily job
    ist = pytz.timezone('Asia/Kolkata')
    time = datetime.time(8, 0, tzinfo=ist)
    
    application.job_queue.run_daily(
        send_daily_vocab,
        time=time,
        name="daily_vocab"
    )
    logger.info(f"Scheduled daily job at {time} IST")

    # Run with webhook
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"{APP_URL}/{BOT_TOKEN}",
        url_path=BOT_TOKEN,
        drop_pending_updates=True
    )

if __name__ == "__main__":
    main()