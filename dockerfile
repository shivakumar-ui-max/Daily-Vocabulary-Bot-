FROM python:3.11

WORKDIR /app

COPY . /app

RUN pip install --upgrade pip

RUN pip install python-telegram-bot apscheduler pymongo python-dotenv

CMD ["python", "vocab_bot.py"]
