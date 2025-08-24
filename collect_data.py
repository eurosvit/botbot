from app.db import get_session
from sqlalchemy import text

def collect_daily_data():
    """
    Збір даних для щоденного звіту.
    """
    session = get_session()
    query = """
    SELECT *
    FROM daily_reports
    WHERE day = CURRENT_DATE - INTERVAL '1 day'
    """
    result = session.execute(text(query)).fetchone()
    if not result:
        raise ValueError("No data found for the report.")
    
    # Безпечне отримання clarity_json
    clarity = getattr(result, 'clarity_json', {}) or {}

    def get_nested(d, *keys, default=None):
        for k in keys:
            if isinstance(d, dict) and k in d:
                d = d[k]
            else:
                return default
        return d

    return {
        "real_sales_amount": getattr(result, "real_sales_amount", 0),
        "real_sales_count": getattr(result, "real_sales_count", 0),
        "processing_amount": getattr(result, "processing_amount", 0),
        "processing_orders_count": getattr(result, "processing_orders_count", 0),
        "cancelled_amount": getattr(result, "cancelled_amount", 0),  # якщо колонки нема, буде 0
        "cancelled_orders_count": getattr(result, "cancelled_orders_count", 0),
        "ad_cost": getattr(result, "ad_cost", 0),
        "manager_cost": getattr(result, "manager_cost", 0),
        "avg_margin": getattr(result, "avg_margin", 0),
        "net_profit": getattr(result, "net_profit", 0),
        "total_orders": getattr(result, "orders_count", 0),
        "orders_ads_count": getattr(result, "orders_ads_count", 0),
        "avg_check": getattr(result, "avg_check", 0),
        # Clarity та поведінка користувачів (з fallback)
        "sessions": clarity.get("sessions", 0),
        "bot_sessions": clarity.get("bot_sessions", 0),
        "real_sessions": clarity.get("real_sessions", 0),
        "unique_users": clarity.get("unique_users", 0),
        "mobile_percentage": clarity.get("mobile_percentage", 0),
        "pc_percentage": clarity.get("pc_percentage", 0),
        "paid_search": get_nested(clarity, "channels", "paid_search", default=0),
        "direct": get_nested(clarity, "channels", "direct", default=0),
        "organic": get_nested(clarity, "channels", "organic", default=0),
        "other": get_nested(clarity, "channels", "other", default=0),
        "referral": get_nested(clarity, "channels", "referral", default=0),
        "top_pages": clarity.get("top_pages", []),
        "top_products": clarity.get("top_products", []),
        "quick_back_clicks": clarity.get("quick_back_clicks", 0),
        "dead_clicks": clarity.get("dead_clicks", 0),
        "js_errors": clarity.get("js_errors", 0),
        "js_error_details": clarity.get("js_error_details", ""),
        "recommendations": clarity.get("recommendations", ""),
        "high_exit_page": clarity.get("high_exit_page", ""),
    }
