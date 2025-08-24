print("=== Daily report worker started ===")

from app.telegram import Telegram
from generate_report import format_daily_report
from collect_data import collect_daily_data

def send_daily_report():
    """
    Формування та надсилання щоденного звіту в Telegram.
    """
    try:
        print("Збираємо дані для звіту...")
        data = collect_daily_data()
        print("Дані зібрані:", data)

        report_text = format_daily_report(data)
        print("Сформований текст звіту:\n", report_text)

        telegram_bot = Telegram()
        print("Telegram бот ініціалізований")

        result = telegram_bot.send(report_text)
        if result:
            print("Report sent successfully!")
        else:
            print("Failed to send report.")
    except Exception as e:
        print(f"Error sending report: {e}")

if __name__ == "__main__":
    send_daily_report()
