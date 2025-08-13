# Render Bot Reset Kit

## Local run
1. `python -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. Copy `.env.example` → `.env` and fill values.
4. `python -m app.main`

Open http://localhost:8000/healthz

## Deploy to Render
- New → **Web Service** → connect repo
- Environment: **Python**
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn -w 1 -b 0.0.0.0:$PORT app.main:app`
- Health Check Path: `/healthz`
- Instance type: Starter is fine to begin
- Env Vars:
  - `SECRET_KEY`
  - `TELEGRAM_BOT_TOKEN`
  - `TELEGRAM_CHAT_ID`
  - `DATABASE_URL` (from Render PostgreSQL add‑on). No need to add `?sslmode=require` — the app will auto‑append if missing.
  - `TZ=Europe/Kyiv`
  - `DAILY_REPORT_CRON=55 23 * * *`

### Post‑deploy tests (in this exact order)
1. Open `/healthz` → should return `{status: ok}`.
2. Open `/trigger/telegram-test` → should send a test message to Telegram.
3. POST a dummy SalesDrive webhook:
   ```bash
   curl -X POST "$RENDER_URL/webhook/salesdrive"      -H 'Content-Type: application/json'      -d '{"test":true,"msg":"hello"}'
   ```
   You should get `ok` and a Telegram ping.
4. Open `/trigger/report-now` → should ping Telegram with a manual report.

### Common pitfalls fixed here
- **Gunicorn import crash** → We import `init_db()` safely and log trace; DB URL SSL is handled.
- **Postgres SSL error** → `sslmode=require` auto‑injected if missing.
- **No Telegram messages** → strict asserts for token/chat ID, HTTP errors logged with stack trace.
- **Timezones** → APScheduler uses `TZ` env (default Europe/Kyiv`).
- **Deprecation of `utcnow()`** → replaced with `datetime.now(timezone.utc)`.

## Next steps
- Add your trading logic inside `utils.py` and routes to execute signals.
- (Optional) Add Alembic for migrations if schema evolves.
