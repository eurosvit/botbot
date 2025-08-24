from app.db import migrate
migrate()

from flask import Flask, Response, request
from app.logging_conf import configure_logging
from app.telegram import Telegram
from collect_data import collect_daily_data
from generate_report import format_daily_report

app = Flask(__name__)
configure_logging()
logger = logging.getLogger(__name__)

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
