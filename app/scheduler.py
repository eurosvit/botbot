import os, logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from .telegram import Telegram
from .utils import utcnow

def create_scheduler(app):
    sched = BackgroundScheduler(timezone=os.getenv("TZ", "Europe/Kyiv"))

    @sched.scheduled_job(CronTrigger.from_crontab(os.getenv("DAILY_REPORT_CRON", "55 23 * * *")))
    def daily_report():
        with app.app_context():
            logging.info({"event":"daily_report_start","ts":utcnow().isoformat()})
            Telegram().send("📊 Daily report: system is alive. (Customize content)")

    return sched
