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
    
    # Форматування даних у словник
    return {
        "real_sales_amount": result.real_sales_amount,
        "real_sales_count": result.real_sales_count,
        "processing_amount": result.processing_amount,
        "processing_orders_count": result.processing_orders_count,
        "cancelled_amount": result.cancelled_amount,
        "cancelled_orders_count": result.cancelled_orders_count,
        "ad_cost": result.ad_cost,
        "manager_cost": result.manager_cost,
        "avg_margin": result.avg_margin,
        "net_profit": result.net_profit,
        "total_orders": result.orders_count,
        "orders_ads_count": result.orders_ads_count,
        "avg_check": result.avg_check,
        # Clarity та поведінка користувачів
        "sessions": result.clarity_json['sessions'],
        "bot_sessions": result.clarity_json['bot_sessions'],
        "real_sessions": result.clarity_json['real_sessions'],
        "unique_users": result.clarity_json['unique_users'],
        "mobile_percentage": result.clarity_json['mobile_percentage'],
        "pc_percentage": result.clarity_json['pc_percentage'],
        "paid_search": result.clarity_json['channels']['paid_search'],
        "direct": result.clarity_json['channels']['direct'],
        "organic": result.clarity_json['channels']['organic'],
        "other": result.clarity_json['channels']['other'],
        "referral": result.clarity_json['channels']['referral'],
        "top_pages": result.clarity_json['top_pages'],
        "top_products": result.clarity_json['top_products'],
        "quick_back_clicks": result.clarity_json['quick_back_clicks'],
        "dead_clicks": result.clarity_json['dead_clicks'],
        "js_errors": result.clarity_json['js_errors'],
        "js_error_details": result.clarity_json['js_error_details'],
        "recommendations": result.clarity_json['recommendations'],
        "high_exit_page": result.clarity_json['high_exit_page']
    }
