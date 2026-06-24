import logging

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
