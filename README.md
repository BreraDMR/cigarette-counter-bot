<div align="center">

# 🚬 Cigarette Counter Bot

**A Telegram bot that makes a smoking habit impossible to ignore — one tap logs a cigarette, then see *when* you smoke most, the money going up in smoke, and a "who's calmest" leaderboard to push you down.**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white&style=for-the-badge)](requirements.txt)
[![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-21.x%20async-2CA5E0?logo=telegram&logoColor=white&style=for-the-badge)](requirements.txt)
[![matplotlib](https://img.shields.io/badge/matplotlib-charts-11557C?style=for-the-badge)](bot/charts.py)
[![SQLite](https://img.shields.io/badge/SQLite-storage-003B57?logo=sqlite&logoColor=white&style=for-the-badge)](bot/db.py)
[![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white&style=for-the-badge)](docker-compose.yml)

</div>

A Telegram bot that counts the cigarettes you smoke. It's fully interactive:
everything is driven by **on-screen buttons**, so there's no syntax to memorize.
One break = one cigarette, logged in a single tap. See clean Excel-style charts
of **when** you smoke, track real spending on **consumables** (tobacco, paper,
filters or packs), compete on a shared leaderboard (where **smoking less ranks you
higher**), and attach a photo to a smoke break. All data lives in SQLite, kept
**separately per user**. Slash commands work too, as a shortcut.

## The problems it solves

- **You can't quit what you don't measure.** One smoke break = one cigarette, and
  the **"Smoke +1"** button logs it instantly — no number to type, no app beyond
  Telegram to install. Logging takes a single tap.
- **A raw count doesn't show your pattern.** All charts live under one **Stats**
  menu: **when** you smoke most (by hour of day, with the peak highlighted), a
  **weekday** breakdown (weekdays vs. weekends), a per-day dynamics histogram, a
  cumulative total, **Intervals** (how long you've gone without one, longest break,
  average gap), and a weekly **Trend** (±%). The point is *time*, not just totals.
- **"A pack costs a bit" hides the real total — and not everyone smokes packs.**
  The **Expenses** view tracks real **consumables**: tobacco, rolling paper,
  filters, or a ready-made pack. You open a unit and record its price; when it runs
  out you mark it done. The bot shows total spent, the price of a single cigarette,
  and a "where the money went" breakdown by consumable. Prices can be in **EUR,
  UAH or CZK** — amounts are **auto-converted** to your chosen currency at an
  approximate live rate (cached, with an offline fallback).
- **Willpower alone fades.** A reverse **leaderboard** (`/top`) ranks participants
  by cigarettes this week — **fewer is higher** — so the social pressure pushes you
  the right way instead of rewarding more.
- **Mistakes happen when you log fast.** You can **edit or delete** your own
  entries from a button list (delete asks for confirmation) — you can only touch
  your own records.
- **One bot, many users.** All data is isolated by `user_id`, so a group can share
  the same bot without seeing each other's raw entries.

## Features

- **Registration with a name** — on the first `/start` the bot asks how to list you
  on the leaderboard (changeable later in **⚙️ Settings**).
- **🚬 Smoke +1** — one button logs one cigarette instantly, no questions asked.
  One break = one cigarette. `/add` does the same.
- **📊 Stats** — a single button opening a menu of cuts:
  - 📋 numeric summary (total, breaks, days, daily average, record, peak hour);
  - 🕐 **by hour of day** — when the urge hits most (peak highlighted);
  - 📅 **by weekday** — weekdays vs. weekends;
  - 📈 per-day dynamics histogram (record day highlighted);
  - 🔥 cumulative total over time;
  - ⏱ intervals — how long without one, longest break, average gap;
  - 📉 weekly trend — this week vs. last (±%).
- **💸 Expenses** — consumables tracking, not just packs: tobacco, paper, filters
  or a ready-made pack. "🆕 Open a unit" records its price; "✅ Unit finished" marks
  it done. The bot shows total spent, the price of one cigarette, and a "where the
  money went" pie by consumable.
- **🏆 Reverse leaderboard** (`/top`) — "who's calmest" this week, **fewer is higher**.
- **✏️ Entries** — the bot shows recent entries as buttons; pick one, then
  "✏️ Change number", "🕐 Change time" or "🗑 Delete" (with confirmation). You can
  only edit your own.
- **🌐 Languages** — the interface is available in **English (default)**, Russian
  and Czech; switch any time in **⚙️ Settings**. New users start in English with
  **EUR** as the default currency.
- **⚙️ Settings** — change your name, currency (EUR / UAH / CZK, with
  auto-conversion of past expenses at an approximate rate) and language.
- **Photos (optional)** — send a photo after a break and it's saved locally
  (`data/photos/<user_id>/`) and attached to the last entry.
- **Multi-user** — data isolated per `user_id`.

## Commands

Buttons are usually enough, but everything is available as a command too:

| Command | Description |
|---|---|
| `/start` | register (asks your name) and open the main menu |
| `/add` | log a smoke break (+1 cigarette) |
| `/stats` | stats menu |
| `/expenses` | expenses menu (consumables) |
| `/top` | weekly leaderboard (fewer is higher) |
| `/edit` | pick an entry and fix/delete it |
| `/settings` | change your name, currency and language |
| `/today` | how many cigarettes today |
| `/cancel` | cancel the current dialog |
| `/help` | help |

## Tech

- Python 3.12
- [python-telegram-bot](https://docs.python-telegram-bot.org) 21.x (async)
- matplotlib — chart rendering
- SQLite — storage
- Docker / docker-compose — deployment

## Running

### 1. Token

Get a token from [@BotFather](https://t.me/BotFather), copy the example config and
paste the token in:

```bash
cp .env.example .env
# edit .env → BOT_TOKEN=...
```

### 2. Docker (recommended)

```bash
docker compose up -d --build
docker compose logs -f
```

The database and photos are stored in the local `./data` folder (mounted to
`/data` inside the container) and survive restarts. The timezone for smoke-break
timestamps is set via `TZ` (default `Europe/Prague`) in `docker-compose.yml` / `.env`.

### 3. Locally without Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export BOT_TOKEN=... DB_PATH=./data/cigarettes.db PHOTO_DIR=./data/photos
python -m bot.main
```

## Structure

```
bot/
  main.py     — command handlers and bot startup
  db.py       — SQLite layer (users, smoke breaks, consumables, photos)
  charts.py   — chart rendering (matplotlib)
Dockerfile
docker-compose.yml
requirements.txt
.env.example
```

## Data

- `data/cigarettes.db` — the SQLite database.
- `data/photos/<user_id>/set_<id>.jpg` — smoke-break photos.

The `data/` folder and `.env` are excluded from git (`.gitignore`) — the token and
personal data never end up in the repository.
