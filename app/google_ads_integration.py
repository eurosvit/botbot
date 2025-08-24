import os
from datetime import datetime, timedelta
from google.ads.google_ads.client import GoogleAdsClient
from google.ads.google_ads.errors import GoogleAdsException
from app.db import get_session  # ДОДАНО

def analyze_google_ads_performance():
    """
    Аналізує ефективність рекламних кампаній за минулий день і записує дані в базу.
    """
    try:
        credentials_path = "google_ads.yaml"
        with open(credentials_path, "w") as f:
            f.write(f"""
developer_token: "{os.getenv('GOOGLE_ADS_DEVELOPER_TOKEN')}"
client_id: "{os.getenv('GOOGLE_ADS_CLIENT_ID')}"
client_secret: "{os.getenv('GOOGLE_ADS_CLIENT_SECRET')}"
refresh_token: "{os.getenv('GOOGLE_ADS_REFRESH_TOKEN')}"
login_customer_id: "{os.getenv('GOOGLE_ADS_LOGIN_CUSTOMER_ID')}"
""")

        google_ads_client = GoogleAdsClient.load_from_storage(credentials_path)
        customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID")
        ga_service = google_ads_client.get_service("GoogleAdsService")
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        query = f"""
        SELECT
          campaign.id,
          campaign.name,
          metrics.clicks,
          metrics.impressions,
          metrics.cost_micros
        FROM
          campaign
        WHERE
          segments.date = '{yesterday}'
        LIMIT
          10
        """
        response = ga_service.search(customer_id=customer_id, query=query)

        print(f"Результати аналізу за {yesterday}:")
        session = get_session()  # Отримуємо сесію для запису

        for row in response:
            cost_micros = row.metrics.cost_micros
            cost = cost_micros / 1_000_000
            campaign_name = row.campaign.name
            clicks = row.metrics.clicks
            impressions = row.metrics.impressions

            print(f"""
Кампанія: {campaign_name}
Кліки: {clicks}
Покази: {impressions}
Витрати: {cost:.2f} UAH
""")
            # Запис у базу (ad_stats)
            session.execute(
                """
                INSERT INTO ad_stats (stat_date, campaign, cost, currency, clicks, impressions)
                VALUES (:date, :camp, :cost, :curr, :clicks, :imp)
                ON CONFLICT (stat_date, campaign) DO UPDATE
                SET cost = EXCLUDED.cost, clicks = EXCLUDED.clicks, impressions = EXCLUDED.impressions
                """,
                {
                    "date": yesterday,
                    "camp": campaign_name,
                    "cost": cost,
                    "curr": "UAH",
                    "clicks": clicks,
                    "imp": impressions,
                }
            )
        session.commit()  # Зберігаємо всі зміни

    except GoogleAdsException as ex:
        print("Google Ads API інтеграція не вдалася.")
        for error in ex.failure.errors:
            print(f"Error: {error.message}")
        return None
    except Exception as e:
        print(f"Інша помилка: {e}")
        return None
    finally:
        if os.path.exists(credentials_path):
            os.remove(credentials_path)

if __name__ == "__main__":
    analyze_google_ads_performance()
