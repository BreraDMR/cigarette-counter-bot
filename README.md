<div align="center">

# 🚬 Cigarette Counter Bot

**A Telegram bot that makes a smoking habit impossible to ignore — log every cigarette in two taps, then see the money, hours and trend going up in smoke, with a "who's calmest" leaderboard to push you down.**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white&style=for-the-badge)](requirements.txt)
[![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-21.x%20async-2CA5E0?logo=telegram&logoColor=white&style=for-the-badge)](requirements.txt)
[![matplotlib](https://img.shields.io/badge/matplotlib-charts-11557C?style=for-the-badge)](bot/charts.py)
[![SQLite](https://img.shields.io/badge/SQLite-storage-003B57?logo=sqlite&logoColor=white&style=for-the-badge)](bot/db.py)
[![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white&style=for-the-badge)](docker-compose.yml)

</div>

A Telegram bot that counts the cigarettes you smoke. It's fully interactive:
everything is driven by **on-screen buttons** and step-by-step dialogs (the bot
asks, you answer), so there's no syntax to memorize. See clean Excel-style charts,
compete with others on a shared leaderboard (where **smoking less ranks you
higher**), and attach a photo to a smoke break. All data lives in SQLite, kept
**separately per user**. Slash commands work too, as a shortcut.

## The problems it solves

- **You can't quit what you don't measure.** Each smoke break — just a number — is
  logged in a guided chat flow ("Log a break" → type how many you smoked), so the
  record takes seconds and there's no app beyond Telegram to install.
- **"A pack costs a bit" hides the real total.** The **"Burned"** view (`/money`)
  turns your habit into concrete **money and hours lost**, with a per-day spending
  chart. Pack price and size are set in **Settings**, so the numbers are yours.
- **A raw count doesn't show whether you're winning.** The bot renders **charts**
  (`matplotlib`): cigarettes per break, a per-day histogram with the record day
  highlighted, and a cumulative total — plus a **Trend** view (`/trend`) comparing
  this week to last (±%), and **Intervals** (`/intervals`): how long you've gone
  without one, your longest streak, and the average gap between breaks.
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
  on the leaderboard (changeable later via "Change name").
- **Logging smoke breaks** — "Log a break" button: the bot asks how many cigarettes
  you smoked and you type the number (or `/add 20`).
- **Charts:**
  - `/chart` — line chart of cigarettes per break;
  - `/days` — per-day histogram (with the record day highlighted);
  - `/total` — cumulative "total so far" chart.
- **💸 Money & time** — "Burned" button (`/money`): money and hours gone up in
  smoke, plus a per-day spending chart. Price and pack size are set in Settings.
- **⏱ Intervals & streaks** — "Intervals" button (`/intervals`): how long you've
  gone without smoking, your longest break, the average gap between breaks.
- **📉 Trend** — "Trend" button (`/trend`): this week vs. last (±%).
- **Stats** — `/today`, `/stats` (total, breaks, days, daily average, record,
  money and time spent).
- **Reverse leaderboard** — "Leaderboard" button (`/top`): "who's calmest" —
  participants ranked by weekly count, **fewer is higher**.
- **⚙️ Settings** — "Settings" button (`/settings`): currency, pack price and
  cigarettes per pack (for the money math).
- **Edit & delete** — "Edit entries" button: the bot shows your recent entries as
  buttons; pick one, then "✏️ Change number" or "🗑 Delete entry" (delete with
  confirmation). You can only edit your own entries; `/edit` works too.
- **Photos (optional)** — send a photo after a break and it's saved locally
  (`data/photos/<user_id>/`) and attached to the last entry.
- **Multi-user** — data isolated per `user_id`.

## Commands

Buttons are usually enough, but everything is available as a command too:

| Command | Description |
|---|---|
| `/start` | register (asks your name) and open the main menu |
| `/setname` | change your leaderboard name |
| `/settings` | currency, pack price and pack size |
| `/add` (or `/add 20`) | log a smoke break — asks for the number, or set it inline |
| `/today` | how many cigarettes today |
| `/money` | money and time gone up in smoke + spending chart |
| `/intervals` | how long without one, breaks between |
| `/trend` | this week vs. last |
| `/total` | cumulative chart over all time |
| `/chart` | cigarettes-per-break chart |
| `/days` | per-day histogram |
| `/stats` | numeric summary |
| `/top` | weekly leaderboard (fewer is higher) |
| `/edit` | pick an entry and fix/delete it |
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
`/data` inside the container) and survive restarts.

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
  db.py       — SQLite layer (users, smoke breaks, photos)
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
