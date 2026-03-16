# Yad2Bot 🏠

Monitors Yad2 for rental apartments in Tel Aviv and sends Telegram alerts for new listings.

## Features

- Polls Yad2 API every 15 minutes (configurable)
- Filters by city, price range, and room count
- Sends formatted Telegram messages with listing details
- SQLite deduplication — no duplicate alerts
- Graceful error handling — never crashes on a single failed request

## Setup

1. Create a Telegram bot via [@BotFather](https://t.me/BotFather) and get the token
2. Get your chat ID by messaging [@userinfobot](https://t.me/userinfobot)
3. Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

4. Install dependencies:

```bash
pip install -r requirements.txt
```

5. Run:

```bash
python main.py
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_TOKEN` | Yes | — | Telegram bot token |
| `TELEGRAM_CHAT_ID` | Yes | — | Telegram chat ID |
| `MAX_PRICE` | No | 9000 | Maximum rent price (₪) |
| `MIN_PRICE` | No | 0 | Minimum rent price (₪) |
| `ROOMS` | No | 3,3.5,4 | Room counts (comma-separated) |
| `CITY_ID` | No | 5000 | Yad2 city ID (5000 = Tel Aviv) |
| `CHECK_INTERVAL_MINUTES` | No | 15 | Poll interval in minutes |

## Deploy to Railway

1. Push this repo to GitHub
2. Create a new project on [Railway](https://railway.app)
3. Connect your GitHub repo
4. Add environment variables in Railway dashboard
5. Railway will auto-detect the `Procfile` and run as a worker
