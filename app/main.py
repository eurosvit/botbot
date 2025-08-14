import os
import logging
import socket
from flask import Flask, Response, request
from app.logging_conf import configure_logging
from app.reporting_ecom import get_daily_ecom_report
from app.salesdrive_webhook import process_salesdrive_webhook
from app.clarity import get_clarity_insights
from app.telegram import Telegram  # Змінено імпорт на клас Telegram
from app.analyze import generate_actionable_insights

app = Flask(__name__)
configure_logging()
logger = logging.getLogger(__name__)

@app.route("/healthz")
def healthz():
    logger.info("Health check requested")
    return {"status": "ok"}

@app.route("/", methods=["GET"])
def index():
    logger.info("Index page requested")
    return Response("Bot service is running!", mimetype="text/plain")

@app.route("/daily_report", methods=["POST", "GET"])
def daily_report():
    logger.info("Daily report requested")

    try:
        logger.info("Getting daily ecommerce report...")
        ecom_data = get_daily_ecom_report()
        logger.debug(f"Ecommerce data: {ecom_data}")

        logger.info("Processing SalesDrive webhook...")
        salesdrive_data = process_salesdrive_webhook()
        logger.debug(f"SalesDrive data: {salesdrive_data}")

        logger.info("Getting Clarity insights...")
        clarity_data = get_clarity_insights()
        logger.debug(f"Clarity data: {clarity_data}")

        logger.info("Generating actionable insights...")
        insights, recommendations = generate_actionable_insights(
            ecom_data=ecom_data,
            salesdrive_data=salesdrive_data,
            clarity_data=clarity_data
        )
        logger.debug(f"Insights: {insights}")
        logger.debug(f"Recommendations: {recommendations}")

        report_text = f"{insights}\n\nРекомендації:\n{recommendations}"

        # Ініціалізація Telegram
        logger.info("Initializing Telegram bot...")
        telegram_bot = Telegram()  # Створення екземпляра класу Telegram

        # Надсилання звіту через Telegram
        logger.info("Sending report to Telegram...")
        result = telegram_bot.send(report_text)  # Виклик методу send
        if result:
            logger.info("Report sent to Telegram successfully.")
        else:
            logger.error("Failed to send report to Telegram.")

        return {"status": "sent", "report": report_text}

    except Exception as e:
        logger.exception("Error in daily_report route")
        return {"status": "error", "message": str(e)}, 500

@app.route("/webhooks/salesdrive", methods=["POST"])
def salesdrive_webhook_route():
    logger.info("SalesDrive webhook called")
    try:
        data = request.get_json(force=True, silent=True)
        logger.debug(f"Incoming SalesDrive webhook data: {data}")
        result = process_salesdrive_webhook(data)
        logger.info("SalesDrive webhook processed successfully")
        return {"status": "ok", "result": result}
    except Exception as e:
        logger.exception("Error processing SalesDrive webhook")
        return {"status": "error", "message": str(e)}, 500

def find_free_port():
    """Find an available port to run the server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

if __name__ == "__main__":
    port = int(os.environ.get("PORT", find_free_port()))
    app.run(host="0.0.0.0", port=port)
