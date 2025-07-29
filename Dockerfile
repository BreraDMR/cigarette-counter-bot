FROM python:3.12-slim

# Cyrillic fonts for the chart labels, tzdata so TZ actually means something
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot ./bot

# The database and the photos live on a volume mounted at /data.
# TZ decides how a break is stamped; override it in compose or .env.
ENV DB_PATH=/data/cigarettes.db \
    PHOTO_DIR=/data/photos \
    TZ=Europe/Prague \
    PYTHONUNBUFFERED=1

CMD ["python", "-m", "bot.main"]
