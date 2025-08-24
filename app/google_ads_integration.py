import os
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def analyze_google_ads_performance():
    """
    Аналізує ефективність рекламних кампаній за минулий день.
    """
    logger.info("Starting Google Ads performance analysis")
    
    try:
        # Перевіряємо наявність всіх необхідних змінних середовища
        required_env_vars = [
            'GOOGLE_ADS_DEVELOPER_TOKEN',
            'GOOGLE_ADS_CLIENT_ID',
            'GOOGLE_ADS_CLIENT_SECRET',
            'GOOGLE_ADS_REFRESH_TOKEN',
            'GOOGLE_ADS_LOGIN_CUSTOMER_ID',
            'GOOGLE_ADS_CUSTOMER_ID'
        ]
        
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        if missing_vars:
            logger.warning(f"Missing Google Ads environment variables: {missing_vars}")
            return {
                "status": "warning",
                "message": "Google Ads integration not configured",
                "total_cost": 0,
                "total_conversions_value": 0,
                "roas": 0
            }
        
        # Імпортуємо Google Ads клієнт тільки якщо всі змінні є
        try:
            from google.ads.google_ads.client import GoogleAdsClient
            from google.ads.google_ads.errors import GoogleAdsException
        except ImportError:
            logger.warning("Google Ads client library not installed")
            return {
                "status": "warning", 
                "message": "Google Ads client library not available",
                "total_cost": 0,
                "total_conversions_value": 0,
                "roas": 0
            }

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
        logger.info("Initializing Google Ads client")
        google_ads_client = GoogleAdsClient.load_from_storage(credentials_path)

        # Створюємо сервіс Google Ads
        customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID")
        ga_service = google_ads_client.get_service("GoogleAdsService")

        # Отримуємо дату минулого дня
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        logger.info(f"Analyzing performance for date: {yesterday}")

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
        
        logger.info("Executing Google Ads query")
        response = ga_service.search(customer_id=customer_id, query=query)

        logger.info(f"Результати аналізу за {yesterday}:")
        total_cost = 0
        total_conversions_value = 0
        campaign_count = 0
        
        for row in response:
            campaign_count += 1
            cost_micros = row.metrics.cost_micros
            cost = cost_micros / 1_000_000  # Конвертуємо мікроси в стандартну валюту
            total_cost += cost
            total_conversions_value += row.metrics.conversions_value

            logger.info(f"""
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
        logger.info(f"Загальні витрати за день: {total_cost:.2f} USD")
        logger.info(f"Загальне значення конверсій за день: {total_conversions_value:.2f} USD")
        logger.info(f"ROAS (Рентабельність витрат на рекламу): {roas:.2f}")
        
        return {
            "status": "success",
            "total_cost": total_cost,
            "total_conversions_value": total_conversions_value,
            "roas": roas,
            "campaigns_analyzed": campaign_count
        }

    except Exception as ex:
        # Handle both GoogleAdsException and other exceptions
        logger.exception(f"Error in Google Ads analysis: {ex}")
        return {
            "status": "error",
            "message": f"Google Ads API error: {str(ex)}",
            "total_cost": 0,
            "total_conversions_value": 0,
            "roas": 0
        }
    finally:
        # Видаляємо тимчасовий файл конфігурації
        credentials_path = "google_ads.yaml"
        if os.path.exists(credentials_path):
            os.remove(credentials_path)
            logger.debug("Temporary credentials file removed")