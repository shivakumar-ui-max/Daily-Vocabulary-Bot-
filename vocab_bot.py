import os
import datetime
import logging
import pytz
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    Application,
    MessageHandler,
    filters,
    ConversationHandler
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

# Conversation states for pronunciation
PRONOUNCE_WORD = 1

def format_word_message(word, index=None):
    """Format word with all details"""
    prefix = f"{index}️⃣ " if index else ""
    return (
        f"{prefix}📖 *Word*: {word.get('English_Word', '')}\n"
        f"*Meaning*: {word.get('English_Meaning', '')}\n"
        f"*Synonyms*: {word.get('English_Synonyms', '')}\n"
        f"*Antonyms*: {word.get('English_Antonyms', '')}\n"
        f"*Examples*:\n- " + "\n- ".join(word.get('English_Examples', '').split(";")) + "\n\n"
        f"{prefix}📖 *పదం*: {word.get('Telugu_Word', '')}\n"
        f"*అర్థం*: {word.get('Telugu_Meaning', '')}\n"
        f"*పర్యాయపదాలు*: {word.get('Telugu_Synonyms', '')}\n"
        f"*విరుద్ధపదాలు*: {word.get('Telugu_Antonyms', '')}\n"
        f"*ఉదాహరణలు*:\n- " + "\n- ".join(word.get('Telugu_Examples', '').split(";")) + "\n"
    )

async def maintain_history(words, now):
    """Maintain 31-day rotating history"""
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
    """Send welcome message"""
    await update.message.reply_text(
        "📚 *Vocabulary Bot*\n"
        "• 2 words daily at 8 AM IST\n"
        "• /history - 31-day calendar\n"
        "• /today - Today's words\n"
        "• /testjob - Trigger manually\n"
        "• /pronounce - Get pronunciation for any word\n\n"
        "Features:\n"
        "- Bilingual English-Telugu vocabulary\n"
        "- 31-day rotating history\n"
        "- Interactive pronunciation",
        parse_mode="Markdown"
    )

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show interactive 31-day history"""
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

        response = "🗓 *31-Day Vocabulary History*\n✦━━━━━━✦❘ 📖 ❘✦━━━━━━✦\n\n"
        
        for day in days:
            date_str = day["_id"]
            words = day["words"][:2]  # Get up to 2 words per day
            
            response += f"📅 *{date_str}*\n"
            for word in words:
                response += f"✨ *{word['English_Word']}* - {word['English_Meaning']}\n"
                response += f"🌸 *{word['Telugu_Word']}* - {word['Telugu_Meaning']}\n"
                response += "⸻⸻⸻\n"
            
            response += "\n"

        await update.message.reply_text(
            response,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"History error: {e}")
        await update.message.reply_text("Error loading history")

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show today's words"""
    today_start = datetime.datetime.now(pytz.timezone('Asia/Kolkata')).replace(
        hour=0, minute=0, second=0, microsecond=0)
    today_words = list(words_collection.find({
        "date_sent": {"$gte": today_start}
    }).limit(2))
    
    if today_words:
        message = "📚 *Today's Vocabulary*\n\n"
        for i, word in enumerate(today_words, 1):
            message += format_word_message(word, i)
            if i < len(today_words):
                message += "\n📖━━━━━━✧❘ 📚 ❘✧━━━━━━📖\n\n"
        
        await update.message.reply_text(
            message,
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("No words sent today yet!")

async def send_daily_vocab(context: ContextTypes.DEFAULT_TYPE):
    """Send daily words"""
    try:
        now = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
        words = list(words_collection.find({"sent": {"$exists": False}}).limit(2))

        if not words:
            logger.warning("No words available")
            await context.bot.send_message(chat_id=CHAT_ID, text="⚠️ No more unsent words!")
            return

        message = "📚 *Daily Vocabulary*\n\n"
        for i, word in enumerate(words, 1):
            message += format_word_message(word, i)
            if i < len(words):
                message += "\n📖━━━━━━✧❘ 📚 ❘✧━━━━━━📖\n\n"
            
            words_collection.update_one(
                {"_id": word["_id"]},
                {"$set": {"sent": True, "date_sent": now}}
            )

        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            parse_mode="Markdown"
        )

        await maintain_history(words, now)

    except Exception as e:
        logger.error(f"Daily send failed: {e}")
        await context.bot.send_message(chat_id=CHAT_ID, text="❌ Error sending words")

async def test_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manual trigger for testing"""
    await update.message.reply_text("🔄 Sending today's words...")
    await send_daily_vocab(context)

async def pronounce_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start pronunciation conversation"""
    await update.message.reply_text(
        "🔊 *Enter the word to pronounce:*\n"
        "(English or Telugu)",
        parse_mode="Markdown"
    )
    return PRONOUNCE_WORD

async def pronounce_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate and send pronunciations"""
    word = update.message.text.strip()
    
    # Detect if word contains Telugu characters
    is_telugu = any('\u0C00' <= char <= '\u0C7F' for char in word)
    
    try:
        # Generate English pronunciation
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as fp_en:
            tts_en = gTTS(text=word, lang="en")
            tts_en.save(fp_en.name)
            fp_en.close()
            
            with open(fp_en.name, "rb") as audio_en:
                await update.message.reply_voice(
                    voice=audio_en,
                    caption=f"English: *{word}*",
                    parse_mode="Markdown"
                )
        
        # Generate Telugu pronunciation if Telugu script detected
        if is_telugu:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as fp_te:
                tts_te = gTTS(text=word, lang="te")
                tts_te.save(fp_te.name)
                fp_te.close()
                
                with open(fp_te.name, "rb") as audio_te:
                    await update.message.reply_voice(
                        voice=audio_te,
                        caption=f"Telugu: *{word}*",
                        parse_mode="Markdown"
                    )
        else:
            await update.message.reply_text("ℹ️ Add Telugu script for Telugu pronunciation.")
    
    except Exception as e:
        logger.error(f"Pronunciation error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")
    finally:
        # Clean up temp files
        if 'fp_en' in locals(): os.unlink(fp_en.name)
        if is_telugu and 'fp_te' in locals(): os.unlink(fp_te.name)
    
    return ConversationHandler.END

async def cancel_pronounce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel pronunciation conversation"""
    await update.message.reply_text("🚫 Pronunciation cancelled.")
    return ConversationHandler.END

async def post_init(application: Application):
    """Initialize webhook"""
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
    """Start the bot"""
    application = ApplicationBuilder() \
        .token(BOT_TOKEN) \
        .defaults(Defaults(parse_mode=ParseMode.MARKDOWN)) \
        .post_init(post_init) \
        .build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("history", history))
    application.add_handler(CommandHandler("today", today))
    application.add_handler(CommandHandler("testjob", test_job))
    
    # Pronunciation conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("pronounce", pronounce_start)],
        states={
            PRONOUNCE_WORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, pronounce_word)],
        },
        fallbacks=[CommandHandler("cancel", cancel_pronounce)],
    )
    application.add_handler(conv_handler)

    # Schedule daily job
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