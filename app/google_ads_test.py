import os
from google.ads.google_ads.client import GoogleAdsClient
from google.ads.google_ads.errors import GoogleAdsException

def test_google_ads_integration():
    """
    Перевіряє доступ до Google Ads API, отримуючи кампанії з акаунта.
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

        # Виконуємо запит для отримання переліку кампаній
        query = """
        SELECT
          campaign.id,
          campaign.name,
          campaign.status
        FROM
          campaign
        LIMIT 10
        """
        response = ga_service.search(customer_id=customer_id, query=query)

        print("Google Ads API інтеграція успішна. Кампанії:")
        for row in response:
            print(f"ID: {row.campaign.id}, Назва: {row.campaign.name}, Статус: {row.campaign.status}")
        return True

    except GoogleAdsException as ex:
        print("Google Ads API інтеграція не вдалася.")
        for error in ex.failure.errors:
            print(f"Error: {error.message}")
        return False
    except Exception as e:
        print(f"Інша помилка: {e}")
        return False

if __name__ == "__main__":
    test_google_ads_integration()
