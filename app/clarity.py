import requests
import os

CLARITY_API_URL = "https://clarity.microsoft.com/api/v1/analytics"

def fetch_clarity_insights():
    """
    Отримує всі доступні інсайти з Microsoft Clarity.
    """
    api_key = os.getenv("CLARITY_API_KEY")
    headers = {"Authorization": f"Bearer {api_key}"}
    
    # Отримання даних трафіку
    response = requests.get(f"{CLARITY_API_URL}/traffic", headers=headers)
    traffic_data = response.json() if response.status_code == 200 else None
    
    # Отримання даних карти кліків
    response = requests.get(f"{CLARITY_API_URL}/click-metrics", headers=headers)
    click_data = response.json() if response.status_code == 200 else None
    
    # Отримання даних карти скролу
    response = requests.get(f"{CLARITY_API_URL}/scroll-depth", headers=headers)
    scroll_data = response.json() if response.status_code == 200 else None
    
    return {
        "traffic": traffic_data,
        "clicks": click_data,
        "scrolls": scroll_data
    }
