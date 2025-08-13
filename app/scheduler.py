import os, logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from .telegram import Telegram
from .reporting_ecom import build_daily_message
from datetime import date

def create_scheduler(app):
    # Якщо користуєшся Render Cron — цей планувальник можна не чіпати
    sched = BackgroundScheduler(timezone=os.getenv("TZ", "Europe/Kyiv"))

    # За замовчуванням вимкнено: щоб не дублювати з Render Cron.
    # Розкоментуй, якщо хочеш мати внутрішній CRON у веб‑сервісі.
    # @sched.scheduled_job(CronTrigger.from_crontab(os.getenv("DAILY_REPORT_CRON", "0 8 * * *")))
    # def daily_report():
    #     with app.app_context():
    #         logging.info({"event":"daily_report_start"})
    #         Telegram().send(build_daily_message(date.today()))

    return sched
