from datetime import date, timedelta
from sqlalchemy import text
from app.db import get_session

def daterange(period):
    """
    Визначає діапазон дат на основі вибраного періоду.
    """
    t = date.today()
    if period == "week":
        return (t - timedelta(days=7), t)
    elif period == "month":
        return (t - timedelta(days=30), t)
    else:
        raise ValueError("Invalid period. Choose 'week' or 'month'.")

def generate_actionable_insights(period):
    """
    Генерує підсумкові дані для заданого періоду.
    """
    start_date, end_date = daterange(period)
    session = get_session()

    # Виконання SQL-запиту
    rows = session.execute(
        text(
            """
            SELECT day, real_sales_count, real_sales_amount, ad_cost, manager_cost, gross_profit, net_profit
            FROM daily_reports
            WHERE day >= :start_date AND day < :end_date
            ORDER BY day
            """
        ),
        {"start_date": start_date, "end_date": end_date},
    ).fetchall()

    # Якщо даних немає
    if not rows:
        return {"message": f"No data available for the {period} period."}

    # Розрахунки
    total_sales = sum(float(row.real_sales_amount) for row in rows)
    net_profit = sum(float(row.net_profit) for row in rows)
    ad_costs = sum(float(row.ad_cost) for row in rows)
    manager_costs = sum(float(row.manager_cost) for row in rows)

    # Формування підсумкових даних
    summary = {
        "period": f"{start_date} — {end_date}",
        "total_sales": total_sales,
        "net_profit": net_profit,
        "ad_costs": ad_costs,
        "manager_costs": manager_costs,
        "daily_data": [
            {
                "day": row.day,
                "sales_count": int(row.real_sales_count),
                "sales_amount": float(row.real_sales_amount),
                "net_profit": float(row.net_profit),
            }
            for row in rows
        ],
    }

    return summary
