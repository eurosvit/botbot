import requests
import os
import logging

CLARITY_API_URL = "https://www.clarity.ms/export-data/api/v1"

logger = logging.getLogger(__name__)

def fetch_clarity_insights(num_of_days=1, dimension1=None, dimension2=None, dimension3=None):
    """
    Отримує інсайти з Microsoft Clarity через Data Export API.
    """
    token = os.getenv("CLARITY_TOKEN")
    if not token:
        logger.error("Clarity API token is missing. Check CLARITY_TOKEN environment variable.")
        return None

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    params = {"numOfDays": num_of_days}
    if dimension1:
        params["dimension1"] = dimension1
    if dimension2:
        params["dimension2"] = dimension2
    if dimension3:
        params["dimension3"] = dimension3

    try:
        logger.info(f"Fetching insights from Clarity API for numOfDays={num_of_days}, dimensions={dimension1}, {dimension2}, {dimension3}")
        response = requests.get(f"{CLARITY_API_URL}/project-live-insights", headers=headers, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        logger.error("Request to Clarity API timed out.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request to Clarity API failed: {e}")
    return None
