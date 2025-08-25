import os
import logging
from datetime import date, timedelta
import requests

from app.salesdrive_webhook import process_salesdrive_webhook

# Змінні з оточення
API_KEY = os.getenv("SALESDRIVE_API_KEY")
BASE_URL = os.getenv("SALESDRIVE_BASE_URL")
WEBHOOK_TOKEN = os.getenv("SALESDRIVE_WEBHOOK_TOKEN")  # Не використовується тут, але залишаю для гнучкості

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fetch_orders(date_from, date_to):
    """
    Отримує замовлення з SalesDrive API за вказаний період.
    """
    url = f"{BASE_URL}/orders"
    params = {
        "api_key": API_KEY,
        "date_from": date_from,
        "date_to": date_to,
    }
    try:
        logger.info(f"Fetching orders from {date_from} to {date_to} at {url}")
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        logger.debug(f"Fetched orders: {data}")
        return data
    except Exception as e:
        logger.error(f"Failed to fetch orders from SalesDrive: {e}")
        return None

def import_salesdrive_orders():
    """
    Основна функція для імпорту замовлень за вчора.
    """
    yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    orders_data = fetch_orders(yesterday, yesterday)
    if not orders_data or "orders" not in orders_data:
        logger.error("No orders fetched for yesterday.")
        return
    logger.info(f"Fetched {len(orders_data['orders'])} orders from SalesDrive.")
    result = process_salesdrive_webhook(orders_data)
    logger.info(f"Webhook processed result: {result}")

if __name__ == "__main__":
    import_salesdrive_orders()
