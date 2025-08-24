import requests
import os
import logging

CLARITY_API_URL = "https://www.clarity.ms/export-data/api/v1"

logger = logging.getLogger(__name__)

def fetch_clarity_insights(num_of_days=1, dimension1=None, dimension2=None, dimension3=None):
    """
    Отримує інсайти з Microsoft Clarity через Data Export API.
    """
    token = os.getenv("CLARITY_TOKEN")
    if not token:
        logger.warning("Clarity API token is missing. Check CLARITY_TOKEN environment variable. Returning mock data.")
        return {
            "sessions": 1200,
            "bot_sessions": 150,
            "real_sessions": 1050,
            "unique_users": 800,
            "mobile_percentage": 65,
            "pc_percentage": 35,
            "channels": {
                "paid_search": 450,
                "direct": 300,
                "organic": 200,
                "other": 70,
                "referral": 30
            },
            "top_pages": [
                {"page": "/", "sessions": 400, "exit_rate": 25},
                {"page": "/products", "sessions": 300, "exit_rate": 15},
                {"page": "/category/electronics", "sessions": 200, "exit_rate": 20}
            ],
            "top_products": [
                {"product": "iPhone 15", "interest": 85, "avg_scroll": 75},
                {"product": "Samsung Galaxy", "interest": 78, "avg_scroll": 65}
            ],
            "quick_back_clicks": 12,
            "dead_clicks": 3,
            "js_errors": 5,
            "js_error_details": ["TypeError on checkout", "Network timeout"],
            "recommendations": [
                "Оптимізуйте швидкість завантаження головної сторінки",
                "Покращіть UX форми оформлення замовлення"
            ],
            "high_exit_page": "/checkout"
        }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    params = {"numOfDays": num_of_days}
    if dimension1:
        params["dimension1"] = dimension1
    if dimension2:
        params["dimension2"] = dimension2
    if dimension3:
        params["dimension3"] = dimension3

    try:
        logger.info(f"Fetching insights from Clarity API for numOfDays={num_of_days}, dimensions={dimension1}, {dimension2}, {dimension3}")
        response = requests.get(f"{CLARITY_API_URL}/project-live-insights", headers=headers, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        logger.error("Request to Clarity API timed out.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request to Clarity API failed: {e}")
    
    # Повертаємо мок дані у випадку помилки
    logger.info("Returning mock Clarity data due to API error")
    return {
        "sessions": 0,
        "bot_sessions": 0,
        "real_sessions": 0,
        "unique_users": 0,
        "mobile_percentage": 50,
        "pc_percentage": 50,
        "channels": {"paid_search": 0, "direct": 0, "organic": 0, "other": 0, "referral": 0},
        "top_pages": [],
        "top_products": [],
        "quick_back_clicks": 0,
        "dead_clicks": 0,
        "js_errors": 0,
        "js_error_details": [],
        "recommendations": ["Налаштуйте Clarity API для отримання аналітики"],
        "high_exit_page": "unknown"
    }
