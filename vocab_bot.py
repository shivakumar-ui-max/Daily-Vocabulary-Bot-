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

async def create_pronunciation_buttons(word_id, include_word=False):
    """Create pronunciation buttons with optional word labels"""
    word = words_collection.find_one({"_id": word_id})
    if not word:
        return None
    
    if include_word:
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    f"🔊 {word['English_Word']}",
                    callback_data=f"pronounce_en_{word_id}"
                ),
                InlineKeyboardButton(
                    f"🔊 {word['Telugu_Word']}",
                    callback_data=f"pronounce_te_{word_id}"
                )
            ]
        ])
    else:
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔊 English", callback_data=f"pronounce_en_{word_id}"),
                InlineKeyboardButton("🔊 Telugu", callback_data=f"pronounce_te_{word_id}")
            ]
        ])

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
        "• /history - 31-day calendar with pronunciation\n"
        "• /today - Today's words\n"
        "• /testjob - Trigger manually\n\n"
        "Click 🔊 buttons to hear word pronunciations!",
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

        for day in days:
            date_str = day["_id"]
            words = day["words"][:2]  # Get up to 2 words per day
            
            message = f"🗓 *{date_str}*\n\n"
            buttons = []
            
            for word in words:
                message += (
                    f"✨ *{word['English_Word']}* - {word['English_Meaning']}\n"
                    f"🌸 *{word['Telugu_Word']}* - {word['Telugu_Meaning']}\n"
                    "⸻⸻⸻\n\n"
                )
                buttons.append([
                    InlineKeyboardButton(
                        f"🔊 {word['English_Word']}",
                        callback_data=f"pronounce_en_{word['_id']}"
                    ),
                    InlineKeyboardButton(
                        f"🔊 {word['Telugu_Word']}",
                        callback_data=f"pronounce_te_{word['_id']}"
                    )
                ])
            
            await update.message.reply_text(
                message,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

    except Exception as e:
        logger.error(f"History error: {e}")
        await update.message.reply_text("Error loading history")

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show today's words with pronunciation"""
    today_start = datetime.datetime.now(pytz.timezone('Asia/Kolkata')).replace(
        hour=0, minute=0, second=0, microsecond=0)
    today_words = list(words_collection.find({
        "date_sent": {"$gte": today_start}
    }).limit(2))
    
    if today_words:
        for i, word in enumerate(today_words, 1):
            reply_markup = await create_pronunciation_buttons(word["_id"])
            await update.message.reply_text(
                format_word_message(word, i),
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
    else:
        await update.message.reply_text("No words sent today yet!")

async def send_daily_vocab(context: ContextTypes.DEFAULT_TYPE):
    """Send daily words with pronunciation"""
    try:
        now = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
        words = list(words_collection.find({"sent": {"$exists": False}}).limit(2))

        if not words:
            logger.warning("No words available")
            await context.bot.send_message(chat_id=CHAT_ID, text="⚠️ No more unsent words!")
            return

        for word in words:
            reply_markup = await create_pronunciation_buttons(word["_id"])
            await context.bot.send_message(
                chat_id=CHAT_ID,
                text=format_word_message(word),
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
            words_collection.update_one(
                {"_id": word["_id"]},
                {"$set": {"sent": True, "date_sent": now}}
            )

        await maintain_history(words, now)

    except Exception as e:
        logger.error(f"Daily send failed: {e}")
        await context.bot.send_message(chat_id=CHAT_ID, text="❌ Error sending words")

async def test_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manual trigger for testing"""
    await update.message.reply_text("🔄 Sending today's words...")
    await send_daily_vocab(context)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all pronunciation button clicks"""
    query = update.callback_query
    await query.answer()
    
    try:
        _, lang, word_id = query.data.split('_')
        word = words_collection.find_one({"_id": word_id})
        
        if not word:
            await query.edit_message_text("Word not found")
            return

        text = word['English_Word'] if lang == 'en' else word['Telugu_Word']
        lang_code = 'te' if lang == 'te' else 'en'
        
        with tempfile.NamedTemporaryFile(suffix='.mp3') as fp:
            tts = gTTS(text=text, lang=lang_code)
            tts.save(fp.name)
            await context.bot.send_voice(
                chat_id=query.message.chat_id,
                voice=open(fp.name, 'rb'),
                reply_to_message_id=query.message.message_id
            )
            
    except Exception as e:
        logger.error(f"Pronunciation error: {e}")
        await query.edit_message_text("Error generating pronunciation")

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
    
    # Button click handler
    application.add_handler(CallbackQueryHandler(button_callback))

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