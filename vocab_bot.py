import os
import datetime
from flask import Flask, request
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import Update
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
CHAT_ID = os.getenv("CHAT_ID")
APP_URL = os.getenv("APP_URL")

client = MongoClient(MONGO_URI)
db = client.vocab_bot
words_collection = db.words

app = Flask(__name__)

telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🙏 Welcome to Daily Vocabulary Bot!\n"
        "Every day at 8 AM, you will receive 2 new vocabulary words automatically.\n"
        "Use /history to see past words."
    )

# /history
async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

# Daily job
async def send_daily_vocab(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    today_words = words_collection.find_one({"date": today})
    if not today_words:
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

# Telegram webhook handler
@app.post(f"/{BOT_TOKEN}")
async def webhook_handler():
    data = request.get_json(force=True)
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return "OK"

# Main function
async def main():
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("history", history))

    telegram_app.job_queue.run_daily(
        send_daily_vocab,
        time=datetime.time(hour=8, minute=0),
    )

    webhook_url = f"{APP_URL}/{BOT_TOKEN}"
    await telegram_app.bot.set_webhook(url=webhook_url)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
