import os, logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from .telegram import Telegram
from .reporting_ecom import get_daily_ecom_report
from .salesdrive_webhook import process_salesdrive_webhook
from .clarity import fetch_clarity_insights
from analyze import generate_actionable_insights
from datetime import date

logger = logging.getLogger(__name__)

def create_scheduler(app):
    """
    Створює планувальник для автоматичних завдань.
    """
    sched = BackgroundScheduler(timezone=os.getenv("TZ", "Europe/Kyiv"))
    
    # Увімкнено планувальник для щоденних звітів
    enable_scheduler = os.getenv("ENABLE_SCHEDULER", "true").lower() == "true"
    
    if enable_scheduler:
        logger.info("Scheduler enabled - setting up daily report job")
        
        @sched.scheduled_job(CronTrigger.from_crontab(os.getenv("DAILY_REPORT_CRON", "0 8 * * *")))
        def daily_report_job():
            """
            Щоденне завдання для відправки звіту в Telegram.
            """
            with app.app_context():
                try:
                    logger.info("Starting daily report job")
                    
                    # Збір даних з різних джерел
                    logger.info("Collecting ecommerce data...")
                    ecom_data = get_daily_ecom_report()
                    
                    logger.info("Processing SalesDrive data...")
                    salesdrive_data = process_salesdrive_webhook()
                    
                    logger.info("Fetching Clarity insights...")
                    clarity_data = fetch_clarity_insights()
                    
                    logger.info("Analyzing Google Ads performance...")
                    from .google_ads_integration import analyze_google_ads_performance
                    google_ads_data = analyze_google_ads_performance()
                    
                    # Генерація інсайтів та рекомендацій
                    logger.info("Generating actionable insights...")
                    insights, recommendations = generate_actionable_insights(
                        ecom_data=ecom_data,
                        salesdrive_data=salesdrive_data,
                        clarity_data=clarity_data,
                        google_ads_data=google_ads_data
                    )
                    
                    # Формування звіту
                    report_date = date.today().strftime("%d.%m.%Y")
                    report_text = f"""🤖 Щоденний звіт за {report_date}

{insights}

🎯 Рекомендації на сьогодні:
{recommendations}

Гарного дня та продуктивної роботи! 💪"""
                    
                    # Відправка в Telegram
                    logger.info("Sending report to Telegram...")
                    telegram_bot = Telegram()
                    result = telegram_bot.send(report_text)
                    
                    if result:
                        logger.info("Daily report sent successfully!")
                    else:
                        logger.error("Failed to send daily report")
                        
                except Exception as e:
                    logger.exception(f"Error in daily report job: {e}")
    else:
        logger.info("Scheduler disabled - skipping daily report job setup")

    return sched
