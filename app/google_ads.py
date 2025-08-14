import requests
import os
import logging

logger = logging.getLogger(__name__)

def check_google_ads_integration():
    """
    Makes a test API call to fetch campaign data from Google Ads API.
    Returns campaign data or None if there's an error.
    """
    # Get credentials from environment variables
    client_id = os.getenv("GOOGLE_ADS_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_ADS_CLIENT_SECRET")
    customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID")
    developer_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")
    login_customer_id = os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID")
    refresh_token = os.getenv("GOOGLE_ADS_REFRESH_TOKEN")
    
    # Check if all required credentials are present
    missing_creds = []
    if not client_id:
        missing_creds.append("GOOGLE_ADS_CLIENT_ID")
    if not client_secret:
        missing_creds.append("GOOGLE_ADS_CLIENT_SECRET")
    if not customer_id:
        missing_creds.append("GOOGLE_ADS_CUSTOMER_ID")
    if not developer_token:
        missing_creds.append("GOOGLE_ADS_DEVELOPER_TOKEN")
    if not refresh_token:
        missing_creds.append("GOOGLE_ADS_REFRESH_TOKEN")
    
    if missing_creds:
        logger.error(f"Google Ads credentials are missing: {', '.join(missing_creds)}")
        return None
    
    try:
        # Step 1: Get access token using refresh token
        logger.info("Getting Google Ads access token")
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        
        token_response = requests.post(token_url, data=token_data)
        if token_response.status_code != 200:
            logger.error(f"Failed to get access token: {token_response.status_code} - {token_response.text}")
            return None
        
        access_token = token_response.json().get("access_token")
        if not access_token:
            logger.error("No access token received from Google")
            return None
        
        logger.info("Successfully obtained access token")
        
        # Step 2: Make test API call to fetch campaigns
        logger.info("Fetching campaign data from Google Ads API")
        
        # Prepare headers for Google Ads API
        headers = {
            "Authorization": f"Bearer {access_token}",
            "developer-token": developer_token,
            "Content-Type": "application/json"
        }
        
        # Add login-customer-id header if provided
        if login_customer_id:
            headers["login-customer-id"] = login_customer_id
        
        # Google Ads API endpoint for campaigns
        api_url = f"https://googleads.googleapis.com/v17/customers/{customer_id}/googleAds:search"
        
        # Query to get basic campaign information
        query = {
            "query": """
                SELECT 
                    campaign.id,
                    campaign.name,
                    campaign.status,
                    campaign.advertising_channel_type,
                    metrics.cost_micros,
                    metrics.clicks,
                    metrics.impressions
                FROM campaign 
                WHERE segments.date DURING TODAY
                ORDER BY campaign.name
                LIMIT 10
            """
        }
        
        logger.debug(f"Making API request to: {api_url}")
        ads_response = requests.post(api_url, headers=headers, json=query)
        
        if ads_response.status_code == 200:
            campaigns_data = ads_response.json()
            logger.info(f"Successfully fetched Google Ads data")
            
            # Process and log campaign details
            results = campaigns_data.get("results", [])
            logger.info(f"Found {len(results)} campaigns")
            
            processed_campaigns = []
            for result in results:
                campaign = result.get("campaign", {})
                metrics = result.get("metrics", {})
                
                campaign_info = {
                    "id": campaign.get("id"),
                    "name": campaign.get("name"),
                    "status": campaign.get("status"),
                    "type": campaign.get("advertisingChannelType"),
                    "cost_micros": metrics.get("costMicros", "0"),
                    "clicks": metrics.get("clicks", "0"),
                    "impressions": metrics.get("impressions", "0")
                }
                
                processed_campaigns.append(campaign_info)
                logger.debug(f"Campaign: {campaign_info['name']} - Status: {campaign_info['status']} - Clicks: {campaign_info['clicks']}")
            
            return {
                "status": "success",
                "campaigns": processed_campaigns,
                "total_campaigns": len(processed_campaigns)
            }
        else:
            logger.error(f"Google Ads API request failed: {ads_response.status_code} - {ads_response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error fetching Google Ads data: {e}")
        logger.exception("Google Ads integration error details")
        return None