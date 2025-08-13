# UAH E‑com Analytics Kit — v5
- Реальні продажі (по `shipped_at` + статус), "в процесі", чистий прибуток UAH
- Щоденний Telegram‑звіт о 08:00 (Render cron: `python daily_report.py`)
- Clarity Data Export API — JSON кеш у БД
- Shell: `python analyze.py --period week|month`