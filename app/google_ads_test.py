import os
from datetime import datetime, timedelta
from google.ads.google_ads.client import GoogleAdsClient
from google.ads.google_ads.errors import GoogleAdsException

def analyze_google_ads_performance():
    """
    Аналізує ефективність рекламних кампаній за минулий день.
    """
    try:
        # Завантажуємо конфігурацію з середовища
        credentials_path = "google_ads.yaml"
        with open(credentials_path, "w") as f:
            f.write(f"""
developer_token: "{os.getenv('GOOGLE_ADS_DEVELOPER_TOKEN')}"
client_id: "{os.getenv('GOOGLE_ADS_CLIENT_ID')}"
client_secret: "{os.getenv('GOOGLE_ADS_CLIENT_SECRET')}"
refresh_token: "{os.getenv('GOOGLE_ADS_REFRESH_TOKEN')}"
login_customer_id: "{os.getenv('GOOGLE_ADS_LOGIN_CUSTOMER_ID')}"
""")

        # Ініціалізація клієнта Google Ads
        google_ads_client = GoogleAdsClient.load_from_storage(credentials_path)

        # Створюємо сервіс Google Ads
        customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID")
        ga_service = google_ads_client.get_service("GoogleAdsService")

        # Отримуємо дату минулого дня
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        # Виконуємо запит для отримання метрик ефективності кампаній
        query = f"""
        SELECT
          campaign.id,
          campaign.name,
          metrics.clicks,
          metrics.impressions,
          metrics.ctr,
          metrics.average_cpc,
          metrics.cost_micros,
          metrics.conversions,
          metrics.conversions_value
        FROM
          campaign
        WHERE
          segments.date = '{yesterday}'
        LIMIT
          10
        """
        response = ga_service.search(customer_id=customer_id, query=query)

        print(f"Результати аналізу за {yesterday}:")
        total_cost = 0
        total_conversions_value = 0
        for row in response:
            cost_micros = row.metrics.cost_micros
            cost = cost_micros / 1_000_000  # Конвертуємо мікроси в стандартну валюту
            total_cost += cost
            total_conversions_value += row.metrics.conversions_value

            print(f"""
Кампанія: {row.campaign.name} (ID: {row.campaign.id})
Кліки: {row.metrics.clicks}
Покази: {row.metrics.impressions}
CTR: {row.metrics.ctr:.2f}%
Середня ціна за клік: {row.metrics.average_cpc:.2f} USD
Витрати: {cost:.2f} USD
Конверсії: {row.metrics.conversions}
Значення конверсій: {row.metrics.conversions_value:.2f} USD
""")

        roas = total_conversions_value / total_cost if total_cost > 0 else 0
        print(f"Загальні витрати за день: {total_cost:.2f} USD")
        print(f"Загальне значення конверсій за день: {total_conversions_value:.2f} USD")
        print(f"ROAS (Рентабельність витрат на рекламу): {roas:.2f}")
        return {
            "total_cost": total_cost,
            "total_conversions_value": total_conversions_value,
            "roas": roas
        }

    except GoogleAdsException as ex:
        print("Google Ads API інтеграція не вдалася.")
        for error in ex.failure.errors:
            print(f"Error: {error.message}")
        return None
    except Exception as e:
        print(f"Інша помилка: {e}")
        return None
    finally:
        # Видаляємо тимчасовий файл конфігурації
        if os.path.exists(credentials_path):
            os.remove(credentials_path)

if __name__ == "__main__":
    analyze_google_ads_performance()
