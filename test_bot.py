#!/usr/bin/env python3
"""
Test script to demonstrate BotBot functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.reporting_ecom import get_daily_ecom_report
from app.salesdrive_webhook import process_salesdrive_webhook
from app.clarity import fetch_clarity_insights
from app.google_ads_integration import analyze_google_ads_performance
from analyze import generate_actionable_insights

def test_data_collection():
    """Test all data collection functions"""
    print("🔄 Testing data collection from all services...")
    
    print("\n📊 Testing E-commerce reporting...")
    ecom_data = get_daily_ecom_report()
    print(f"✅ E-commerce data: {len(ecom_data)} fields collected")
    
    print("\n📞 Testing SalesDrive webhook processing...")
    salesdrive_data = process_salesdrive_webhook()
    print(f"✅ SalesDrive data: {salesdrive_data['total_orders']} orders processed")
    
    print("\n🖱️ Testing Microsoft Clarity insights...")
    clarity_data = fetch_clarity_insights()
    print(f"✅ Clarity data: {clarity_data['sessions']} sessions analyzed")
    
    print("\n📱 Testing Google Ads performance...")
    google_ads_data = analyze_google_ads_performance()
    print(f"✅ Google Ads data: Status = {google_ads_data['status']}")
    
    return ecom_data, salesdrive_data, clarity_data, google_ads_data

def test_insights_generation(ecom_data, salesdrive_data, clarity_data, google_ads_data):
    """Test insights and recommendations generation"""
    print("\n🧠 Testing insights generation...")
    
    insights, recommendations = generate_actionable_insights(
        ecom_data=ecom_data,
        salesdrive_data=salesdrive_data,
        clarity_data=clarity_data,
        google_ads_data=google_ads_data
    )
    
    print("\n📈 Generated Insights:")
    print(insights)
    
    print("\n💡 Generated Recommendations:")
    print(recommendations)
    
    return insights, recommendations

def main():
    """Main test function"""
    print("🤖 BotBot Test Suite")
    print("="*50)
    
    try:
        # Test data collection
        ecom_data, salesdrive_data, clarity_data, google_ads_data = test_data_collection()
        
        # Test insights generation
        insights, recommendations = test_insights_generation(
            ecom_data, salesdrive_data, clarity_data, google_ads_data
        )
        
        print("\n🎉 All tests passed successfully!")
        print("\nThe bot is ready to:")
        print("• Collect data from all configured services")
        print("• Generate actionable insights")
        print("• Provide specific recommendations")
        print("• Send daily reports to Telegram (when configured)")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())