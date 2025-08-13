# Render Bot Reset Kit — Variant A (psycopg v3, Python 3.13-ready)

This variant uses **psycopg v3** (binary) and SQLAlchemy URL scheme `postgresql+psycopg://` to avoid psycopg2 issues on Python 3.13.

## Local run
1. `python -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. Copy `.env.example` → `.env` and fill values.
4. `python -m app.main`
Open http://localhost:8000/healthz

## Deploy to Render
- Build: `pip install -r requirements.txt`
- Start: `gunicorn -w 1 -b 0.0.0.0:$PORT app.main:app`
- Health Check: `/healthz`
- Env Vars: `SECRET_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `DATABASE_URL`, `TZ`, `DAILY_REPORT_CRON`

## Notes
- DB URL is coerced to `postgresql+psycopg://` and `sslmode=require` is appended when missing.
