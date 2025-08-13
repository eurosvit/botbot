# Standalone daily report script for Render Cron Job
import os
from datetime import date, timedelta
from app.reporting_ecom import build_daily_message
from app.telegram import Telegram
from app.db import init_db

def main():
    init_db()
    # Звіт за вчорашній день
    day = date.today() - timedelta(days=1)
    txt = build_daily_message(day)
    Telegram().send(txt)
    print("Sent daily report for", day)

if __name__ == "__main__":
    main()
