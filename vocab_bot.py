import os
import datetime
from flask import Flask, request
from pymongo import MongoClient
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    Dispatcher,
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
CHAT_ID = os.getenv("CHAT_ID")
APP_URL = os.getenv("APP_URL")
PORT = int(os.environ.get("PORT", "10000"))

client = MongoClient(MONGO_URI)
db = client.vocab_bot
words_collection = db.words

app = Flask(__name__)

telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()
dispatcher: Dispatcher = telegram_app.dispatcher

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🙏 Welcome to Daily Vocabulary Bot!\n"
        "Every day at 8 AM, you will receive 2 new vocabulary words automatically.\n"
        "Use /history to see past words."
    )

# /history command
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

# Daily vocab sender
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

# Flask route for webhook
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    telegram_app.update_queue.put(update)
    return "OK"

# Set webhook before app starts
@app.before_first_request
def setup():
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("history", history))

    telegram_app.job_queue.run_daily(
        send_daily_vocab,
        time=datetime.time(hour=8, minute=0),
    )

    telegram_app.bot.set_webhook(url=f"{APP_URL}/{BOT_TOKEN}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
