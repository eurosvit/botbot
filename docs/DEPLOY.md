# Безкоштовний деплой торгового бота (paper) 24/7

Схема: **Neon** (безкоштовна Postgres) + **Render Web Service** (free) +
**cron-job.org** (безкоштовний пінгер). Пінгер кожні ~10 хв смикає
`/trading/run` — це й будить free-сервіс, і запускає одну ітерацію торгівлі.

> Усе в paper-режимі: реальні ціни, віртуальні гроші. Нуль фінансового ризику.

---

## Крок 1. База даних — Neon (2 хв)
1. Зайди на **https://neon.tech** → Sign up (можна через Google/GitHub).
2. Create Project → назва будь-яка → Region обери ближчий (EU).
3. Скопіюй **Connection string** (виглядає як
   `postgresql://user:pass@ep-xxxx.eu-central-1.aws.neon.tech/neondb?sslmode=require`).
   Це і є твій `DATABASE_URL`.

## Крок 2. Веб-сервіс — Render (5 хв)

**Варіант Blueprint (простіше):**
1. Зайди на **https://render.com** → New → **Blueprint**.
2. Підключи GitHub-репозиторій `eurosvit/botbot`.
3. Render знайде `render.yaml`. У полі **DATABASE_URL** встав рядок із Neon.
4. (Бажано) зміни `name: trader-mvp` у `render.yaml` на свою унікальну назву.
5. Apply → дочекайся «Live».

**Варіант вручну (якщо Blueprint не підхопився):**
1. New → **Web Service** → репозиторій `eurosvit/botbot`.
2. Branch: `claude/trading-service-mvp-tcrrer`
3. Runtime: Python · Build: `pip install -r requirements.txt` ·
   Start: `gunicorn app.main:app`
4. Plan: **Free**.
5. Environment → додай змінні:
   - `DATABASE_URL` = рядок із Neon
   - `PYTHON_VERSION` = `3.13.0`
   - `TRADE_MODE` = `paper`
   - `TRADE_EXCHANGE` = `binance` (якщо не працює — `kraken`)
   - `TRADE_SYMBOLS` = `BTC/USDT,ETH/USDT`
   - `TRADE_TIMEFRAME` = `15m`
   - `TRADE_PAPER_BALANCE` = `1000`
   - `TRADE_RUN_TOKEN` = вигадай довгий пароль (захист ендпоінта)
6. Create Web Service → дочекайся «Live».

Адреса буде на кшталт `https://trader-mvp.onrender.com`.
Перевір дашборд: `https://<твоя-назва>.onrender.com/trading/dashboard`

## Крок 3. Пінгер — cron-job.org (3 хв)
Free-сервіс Render «засинає» без активності, тож хай його будить пінгер,
заодно запускаючи торгівлю:
1. **https://cron-job.org** → Sign up → Create cronjob.
2. **URL:** `https://<твоя-назва>.onrender.com/trading/run?token=<TRADE_RUN_TOKEN>`
   (якщо токен не задавала — просто `.../trading/run`).
3. **Schedule:** Every 10 minutes.
4. Save. Готово — бот «оживає».

## Крок 4. Спостерігай
- Дашборд: `/trading/dashboard` — крива капіталу, угоди, кнопка оптимізації.
- Статус JSON: `/trading/status`.
- Перші угоди з'являться, коли стратегія дасть сигнал (на `15m` — зазвичай
  від кількох годин до доби).

---

## Часті питання
- **Binance не відповідає (NetworkError)** → постав `TRADE_EXCHANGE=kraken`
  (або `bybit`/`kucoin`/`okx`) і збережи — Render перерозгорнеться сам.
- **Хочу сповіщення в Telegram** → `TRADE_NOTIFY=true` + `TG_BOT_TOKEN` +
  `TG_CHAT_ID`.
- **Перейти на реальні гроші пізніше** → це окрема свідома дія: `TRADE_MODE=live`,
  `TRADE_API_KEY/SECRET`, спершу `TRADE_TESTNET=true`. Не раніше, ніж paper
  покаже адекватні результати.
- **Хочу справжній 24/7 без пінгера** → зроби сервіс типу Background Worker
  (платний, ~$7/міс) зі Start `python -m app.trading.runner`.
