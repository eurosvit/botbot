# UAH E‑com Analytics Kit — v2 (AI‑light, TG_BOT_TOKEN/TG_CHAT_ID)

Що входить:
- Flask API для прийому SalesDrive та ручного звіту.
- Інжест витрат Google Ads через POST (UAH).
- Щоденний звіт з евристичними рекомендаціями (AI‑light).
- Окремий скрипт `daily_report.py` для Render Cron Job (запускає звіт за вчора).

ENV (Render → Environment):
- TG_BOT_TOKEN, TG_CHAT_ID, SECRET_KEY
- TZ=Europe/Kyiv, CURRENCY=UAH
- BRAND_MARGINS_UAH (JSON), DEFAULT_MARGIN_UAH=0.30

Web Service (Render):
- Build: `pip install -r requirements.txt`
- Start: `gunicorn -w 1 -b 0.0.0.0:$PORT app.main:app`
- Health: `/healthz`

Cron Job (Render):
- Command: `python daily_report.py`
- Schedule: 08:00 щодня (у Render scheduler).
