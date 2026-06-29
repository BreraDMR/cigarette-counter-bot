FROM python:3.12-slim

# Шрифты для кириллицы в графиках + tzdata, чтобы работал часовой пояс (TZ)
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot ./bot

# Данные (БД и фото) монтируются как volume в /data.
# TZ — часовой пояс для времени перекуров (можно переопределить в docker-compose/.env)
ENV DB_PATH=/data/cigarettes.db \
    PHOTO_DIR=/data/photos \
    TZ=Europe/Prague \
    PYTHONUNBUFFERED=1

CMD ["python", "-m", "bot.main"]
