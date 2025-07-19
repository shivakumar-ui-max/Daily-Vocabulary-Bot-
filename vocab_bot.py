from dotenv import load_dotenv
load_dotenv()

import os
import random
from datetime import datetime, timedelta
from pymongo import MongoClient
from telegram.ext import Updater, CommandHandler
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone

# MongoDB Setup
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["vocab_bot"]
words_col = db["words"]
history_col = db["history"]

def send_daily(context):
    chat_id = os.getenv("CHAT_ID")
    today = datetime.now().strftime("%Y-%m-%d")

    unused_words = list(words_col.find({"is_used": False}))
    if len(unused_words) < 2:
        context.bot.send_message(chat_id, "🎉 All vocabulary words have been completed!")
        return

    selected = random.sample(unused_words, 2)
    message = "📚 **Daily Vocabulary**\n\n"

    for idx, word in enumerate(selected, 1):
        message += f"{idx}️⃣\n"
        message += f"WORD: {word['word']}\n"
        message += f"MEANING: {word['meaning_en']}\n"
        message += f"SYNONYMS: {', '.join(word['synonyms_en'])}\n"
        message += f"ANTONYMS: {', '.join(word['antonyms_en'])}\n"
        message += f"EXAMPLES:\n"
        for ex in word['examples_en']:
            message += f"- {ex}\n"

        message += f"\nWORD: {word['word_te']}\n"
        message += f"MEANING: {word['meaning_te']}\n"
        message += f"SYNONYMS: {', '.join(word['synonyms_te'])}\n"
        message += f"ANTONYMS: {', '.join(word['antonyms_te'])}\n"
        message += f"EXAMPLES:\n"
        for ex in word['examples_te']:
            message += f"- {ex}\n"

        message += "\n"

        words_col.update_one({"_id": word["_id"]}, {"$set": {"is_used": True}})

    history_col.insert_one({
        "date": today,
        "words": [w['word'] for w in selected]
    })

    cutoff_date = datetime.now() - timedelta(days=30)
    history_col.delete_many({"date": {"$lt": cutoff_date.strftime("%Y-%m-%d")}})

    context.bot.send_message(chat_id=chat_id, text=message)

def history(update, context):
    records = history_col.find().sort("date", 1)
    message = "📜 **Last 30 Days Vocabulary History:**\n"
    for rec in records:
        message += f"{rec['date']}: {', '.join(rec['words'])}\n"
    update.message.reply_text(message)

def start(update, context):
    update.message.reply_text("🙏 Welcome to Daily Vocabulary Bot!\nUse /history to view the last 30 days of words.")

def main():
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("history", history))
    
    india_tz = timezone('Asia/Kolkata')
    # Scheduler setup
    scheduler = BackgroundScheduler()
    india_tz = timezone('Asia/Kolkata')
    scheduler.add_job(send_daily, 'cron', hour=8, minute=0, timezone=india_tz, args=[updater.bot])
    scheduler.start()

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
