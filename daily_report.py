from app.telegram import Telegram
from generate_report import format_daily_report
from collect_data import collect_daily_data

def send_daily_report():
    """
    Формування та надсилання щоденного звіту в Telegram.
    """
    try:
        data = collect_daily_data()
        report_text = format_daily_report(data)

        telegram_bot = Telegram()
        result = telegram_bot.send(report_text)
        if result:
            print("Report sent successfully!")
        else:
            print("Failed to send report.")
    except Exception as e:
        print(f"Error sending report: {e}")
