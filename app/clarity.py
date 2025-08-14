import requests
import os
import logging

CLARITY_API_URL = "https://clarity.microsoft.com/api/v1"

logger = logging.getLogger(__name__)

def fetch_clarity_insights():
    """
    Отримує всі доступні інсайти з Microsoft Clarity.
    """
    project_id = os.getenv("CLARITY_PROJECT_ID")
    token = os.getenv("CLARITY_TOKEN")
    if not project_id or not token:
        logger.error("Clarity credentials are missing: check CLARITY_PROJECT_ID and CLARITY_TOKEN")
        return None

    headers = {"Authorization": f"Bearer {token}"}
    try:
        logger.info("Fetching traffic data from Clarity")
        traffic_response = requests.get(f"{CLARITY_API_URL}/projects/{project_id}/traffic", headers=headers)
        traffic_data = traffic_response.json() if traffic_response.status_code == 200 else {}

        logger.info("Fetching click metrics from Clarity")
        click_response = requests.get(f"{CLARITY_API_URL}/projects/{project_id}/clicks", headers=headers)
        click_data = click_response.json() if click_response.status_code == 200 else {}

        logger.info("Fetching scroll depth data from Clarity")
        scroll_response = requests.get(f"{CLARITY_API_URL}/projects/{project_id}/scroll", headers=headers)
        scroll_data = scroll_response.json() if scroll_response.status_code == 200 else {}

        return {
            "traffic": traffic_data,
            "clicks": click_data,
            "scrolls": scroll_data,
        }
    except Exception as e:
        logger.error(f"Error fetching Clarity data: {e}")
        return None

def get_clarity_insights():
    """
    Wrapper function for compatibility with main.py
    """
    return fetch_clarity_insights()
