# Google Ads API Integration

This file provides integration with Google Ads API for fetching campaign data and metrics.

## Environment Variables

The following environment variables must be set for the Google Ads integration to work:

### Required:
- `GOOGLE_ADS_CLIENT_ID` - OAuth2 client ID from Google Cloud Console
- `GOOGLE_ADS_CLIENT_SECRET` - OAuth2 client secret from Google Cloud Console  
- `GOOGLE_ADS_CUSTOMER_ID` - Your Google Ads customer ID (without dashes)
- `GOOGLE_ADS_DEVELOPER_TOKEN` - Developer token from Google Ads account
- `GOOGLE_ADS_REFRESH_TOKEN` - OAuth2 refresh token

### Optional:
- `GOOGLE_ADS_LOGIN_CUSTOMER_ID` - Manager account customer ID (if using MCC)

## Setup Instructions

1. **Create Google Cloud Project:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one
   - Enable Google Ads API

2. **Configure OAuth2:**
   - Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client IDs"
   - Choose "Web application" 
   - Add redirect URI: `http://localhost:8080/oauth2callback`
   - Save the Client ID and Client Secret

3. **Get Developer Token:**
   - Log into your Google Ads account
   - Go to Tools & Settings → Setup → API Center
   - Apply for developer token access

4. **Generate Refresh Token:**
   - Use Google's OAuth2 playground or write a script to get refresh token
   - Scopes needed: `https://www.googleapis.com/auth/adwords`

5. **Set Environment Variables:**
   ```bash
   export GOOGLE_ADS_CLIENT_ID="your-client-id"
   export GOOGLE_ADS_CLIENT_SECRET="your-client-secret"
   export GOOGLE_ADS_CUSTOMER_ID="1234567890"
   export GOOGLE_ADS_DEVELOPER_TOKEN="your-dev-token"
   export GOOGLE_ADS_REFRESH_TOKEN="your-refresh-token"
   # Optional:
   export GOOGLE_ADS_LOGIN_CUSTOMER_ID="9876543210"
   ```

## Usage

```python
from app.google_ads import check_google_ads_integration

# Test the integration
result = check_google_ads_integration()

if result:
    print(f"Status: {result['status']}")
    print(f"Campaigns found: {result['total_campaigns']}")
    
    for campaign in result['campaigns']:
        print(f"Campaign: {campaign['name']}")
        print(f"  ID: {campaign['id']}")
        print(f"  Status: {campaign['status']}")
        print(f"  Clicks: {campaign['clicks']}")
        print(f"  Impressions: {campaign['impressions']}")
        cost = int(campaign['cost_micros']) / 1_000_000
        print(f"  Cost: {cost:.2f}")
else:
    print("Integration failed - check logs and credentials")
```

## API Response Format

The `check_google_ads_integration()` function returns:

```python
{
    "status": "success",
    "campaigns": [
        {
            "id": "12345",
            "name": "Campaign Name",
            "status": "ENABLED",
            "type": "SEARCH",
            "cost_micros": "1000000",  # Cost in micros (1 UAH = 1,000,000 micros)
            "clicks": "100",
            "impressions": "1000"
        }
    ],
    "total_campaigns": 1
}
```

## Error Handling

The function returns `None` in case of errors and logs detailed information:

- Missing credentials: Returns `None` and logs missing environment variables
- Authentication errors: Returns `None` and logs OAuth2 issues  
- API errors: Returns `None` and logs Google Ads API response errors
- Network errors: Returns `None` and logs connection issues

## Logging

All operations are logged using the standard Python logging module:

- `INFO` level: Normal operations and successful API calls
- `ERROR` level: Error conditions and failures
- `DEBUG` level: Detailed API request/response information

## Integration with Daily Reports

The Google Ads integration can be incorporated into the daily report system by:

1. Calling `check_google_ads_integration()` in the daily report route
2. Including campaign metrics in the insights generation
3. Adding Google Ads data to the Telegram reports

## Troubleshooting

1. **Authentication Errors:**
   - Verify all environment variables are set correctly
   - Check that the refresh token is still valid
   - Ensure developer token is approved and active

2. **API Errors:**
   - Verify customer ID format (no dashes)
   - Check Google Ads account access permissions
   - Ensure API is enabled in Google Cloud Console

3. **Network Errors:**
   - Check internet connectivity
   - Verify firewall settings allow HTTPS connections
   - Check if googleapis.com domains are accessible

## Security Notes

- Store all credentials as environment variables, never in code
- Use secure methods to distribute environment variables in production
- Regularly rotate OAuth2 refresh tokens
- Monitor API usage to detect unauthorized access