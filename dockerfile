# Use Python 3.11 (to avoid weakref error)
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy all project files to /app in container
COPY . .

# Install dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Run the bot when the container starts
CMD ["python", "vocab_bot.py"]
