import logging
import os

from app.db import migrate
migrate()

from flask import Flask, Response, request, redirect
from app.logging_conf import configure_logging
from app.telegram import Telegram
from app.trading.web import bp as trading_bp
from collect_data import collect_daily_data
from generate_report import format_daily_report

app = Flask(__name__)
configure_logging()
logger = logging.getLogger(__name__)

# Торговий модуль: read-only моніторинг + ручний запуск проходу циклу.
app.register_blueprint(trading_bp)

@app.route("/")
def index():
    # Зручний редірект з кореня на торговий дашборд.
    return redirect("/trading/dashboard")

_FAVICON = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
    "<text y='.9em' font-size='90'>📈</text></svg>"
)

@app.route("/favicon.ico")
def favicon():
    return Response(_FAVICON, mimetype="image/svg+xml")


def _scheduled_cycle():
    """Внутрішній планувальник: сам запускає торговий цикл, без зовнішнього пінгера."""
    try:
        from app.trading.config import TradingConfig
        from app.trading.engine import Engine
        from app.trading import store
        from app.utils import utcnow
        cfg = TradingConfig.from_env()
        # Дедуплікація між воркерами + економія БД: не частіше, ніж раз на цикл.
        cycle = int(os.getenv("TRADE_CYCLE_SECONDS", "1800"))
        last = store.last_equity_ts(cfg.mode)
        if last and (utcnow() - last).total_seconds() < cycle * 0.7:
            return
        Engine(cfg).run_once()
    except Exception:
        logger.exception("scheduled cycle failed")


def _scheduled_autotune():
    """Раз на тиждень: авто-тюнінг параметрів на свіжих даних (із дедуплікацією між воркерами)."""
    try:
        from app.trading import store
        if not store.due("_autotune", 6 * 24 * 3600):   # не частіше ~разу на тиждень
            return
        from app.trading.config import TradingConfig
        from app.trading.tuner import autotune, format_autotune
        from app.trading.notify import Notifier
        # Якщо стратегію закріплено — тюнимо лише її параметри, не перемикаючи.
        result = autotune(TradingConfig.from_env(), lock_strategy=store.pinned_strategy())
        Notifier(enabled=True).send(format_autotune(result))
        logger.info("autotune: %s", result)
    except Exception:
        logger.exception("scheduled autotune failed")


def _scheduled_review():
    """Раз на тиждень: само-аналіз результатів у Telegram."""
    try:
        from app.trading import store
        if not store.due("_review", 6 * 24 * 3600):
            return
        from app.trading.config import TradingConfig
        from app.trading.tuner import performance_review
        from app.trading.notify import Notifier
        n = Notifier(enabled=True)
        if n.tg is not None:
            n.send(performance_review(TradingConfig.from_env().mode))
    except Exception:
        logger.exception("scheduled review failed")


if os.getenv("TRADE_SCHEDULER", "true").strip().lower() in ("1", "true", "yes", "on"):
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        # 30 хв за замовч.: рідше звертань до БД → Neon встигає «засинати»
        # і бот вкладається в безкоштовний compute-ліміт. На 1h-таймфреймі якість не страждає.
        _interval = int(os.getenv("TRADE_CYCLE_SECONDS", "1800"))
        _sched = BackgroundScheduler(timezone="UTC")
        _sched.add_job(_scheduled_cycle, "interval", seconds=_interval,
                       max_instances=1, coalesce=True, id="trade_cycle")
        # Самовдосконалення: щотижневий авто-тюнінг та розбір (перевірка щодоби, запуск ~раз на тиждень).
        _sched.add_job(_scheduled_autotune, "interval", hours=24,
                       max_instances=1, coalesce=True, id="autotune")
        _sched.add_job(_scheduled_review, "interval", hours=24,
                       max_instances=1, coalesce=True, id="review")
        _sched.start()
        logger.info("Внутрішній планувальник торгівлі запущено (кожні %s c)", _interval)
    except Exception:
        logger.exception("Не вдалося запустити внутрішній планувальник")

@app.route("/daily_report", methods=["POST", "GET"])
def daily_report():
    logger.info("Daily report requested")
    try:
        data = collect_daily_data()
        logger.debug(f"Aggregated daily data: {data}")
        report_text = format_daily_report(data)
        logger.info("Report text generated")
        telegram_bot = Telegram()
        result = telegram_bot.send(report_text)
        if result:
            logger.info("Report sent to Telegram successfully.")
        else:
            logger.error("Failed to send report to Telegram.")
        return {"status": "sent", "report": report_text}
    except Exception as e:
        logger.exception("Error in daily_report route")
        return {"status": "error", "message": str(e)}, 500
