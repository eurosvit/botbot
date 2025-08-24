#!/usr/bin/env python3
"""
Manual trigger for daily report - useful for testing
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.reporting_ecom import get_daily_ecom_report
from app.salesdrive_webhook import process_salesdrive_webhook
from app.clarity import fetch_clarity_insights
from app.google_ads_integration import analyze_google_ads_performance
from app.telegram import Telegram
from analyze import generate_actionable_insights
from datetime import date
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_manual_report():
    """Manually trigger and send daily report"""
    try:
        logger.info("🤖 Manually triggering daily report...")
        
        # Збір даних з різних джерел
        logger.info("Collecting ecommerce data...")
        ecom_data = get_daily_ecom_report()
        
        logger.info("Processing SalesDrive data...")
        salesdrive_data = process_salesdrive_webhook()
        
        logger.info("Fetching Clarity insights...")
        clarity_data = fetch_clarity_insights()
        
        logger.info("Analyzing Google Ads performance...")
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
        
        print("\n" + "="*50)
        print("📊 DAILY REPORT")
        print("="*50)
        print(report_text)
        print("="*50)
        
        # Спроба відправки в Telegram
        try:
            logger.info("Attempting to send report to Telegram...")
            telegram_bot = Telegram()
            result = telegram_bot.send(report_text)
            
            if result:
                logger.info("✅ Report sent to Telegram successfully!")
            else:
                logger.error("❌ Failed to send report to Telegram")
                
        except RuntimeError as e:
            if "TG creds missing" in str(e):
                logger.warning("⚠️ Telegram credentials not configured - report generated but not sent")
            else:
                raise e
        
        logger.info("✅ Manual report generation completed!")
        return 0
        
    except Exception as e:
        logger.exception(f"❌ Error in manual report generation: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(send_manual_report())