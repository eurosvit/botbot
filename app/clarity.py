import os
import logging
from datetime import date
from app.db import get_session
from app.clarity import fetch_clarity_insights
from sqlalchemy import text

logger = logging.getLogger(__name__)

def save_clarity_to_daily_reports(target_date=None, num_of_days=1):
    """
    Отримує інсайти Clarity і записує їх у поле clarity_json таблиці daily_reports.
    """
    if not target_date:
        target_date = date.today()

    logger.info(f"Fetching Clarity insights for {target_date} (last {num_of_days} days)")
    insights = fetch_clarity_insights(num_of_days=num_of_days)
    if not insights:
        logger.error("No Clarity insights received.")
        return {"status": "error", "message": "No Clarity insights received."}

    session = get_session()
    # Записуємо clarity_json для відповідного дня
    session.execute(
        text("""
            UPDATE daily_reports
            SET clarity_json = :insights
            WHERE day = :d
        """),
        {"insights": insights, "d": target_date}
    )
    session.commit()
    logger.info("Clarity insights successfully saved to daily_reports.")
    return {"status": "ok", "message": "Clarity insights saved.", "date": str(target_date)}

if __name__ == "__main__":
    # Приклад використання: записати інсайти за сьогодні
    result = save_clarity_to_daily_reports()
    print(result)
