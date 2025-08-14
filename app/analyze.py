import logging

logger = logging.getLogger(__name__)

def generate_actionable_insights(ecom_data=None, salesdrive_data=None, clarity_data=None):
    """
    Generates actionable insights based on e-commerce, SalesDrive, and Clarity data.
    
    Args:
        ecom_data: Dictionary with e-commerce financial data
        salesdrive_data: Dictionary with SalesDrive orders data  
        clarity_data: Dictionary with Microsoft Clarity traffic data
        
    Returns:
        tuple: (insights_text, recommendations_text)
    """
    logger.info("Generating actionable insights")
    
    insights = []
    recommendations = []
    
    # Analyze e-commerce data
    if ecom_data:
        logger.debug(f"Processing ecom data: {ecom_data}")
        real_sales = ecom_data.get('real_sales_amount', 0)
        orders_count = ecom_data.get('real_sales_count', 0)
        avg_check = ecom_data.get('real_avg_check', 0)
        ad_cost = ecom_data.get('ad_cost', 0)
        net_profit = ecom_data.get('net_profit', 0)
        
        insights.append(f"💰 Реальні продажі: {orders_count} замовлень на {real_sales:.0f} грн")
        insights.append(f"📊 Середній чек: {avg_check:.0f} грн")
        insights.append(f"💸 Витрати на рекламу: {ad_cost:.0f} грн")
        insights.append(f"✅ Чистий прибуток: {net_profit:.0f} грн")
        
        # Generate recommendations based on e-commerce metrics
        if real_sales > 0 and ad_cost > 0:
            roas = real_sales / ad_cost
            if roas < 3:
                recommendations.append("⚠️ ROAS нижче 3:1. Рекомендується оптимізувати рекламні кампанії")
            elif roas > 5:
                recommendations.append("🚀 Відмінний ROAS! Розгляньте збільшення рекламного бюджету")
    
    # Analyze SalesDrive data
    if salesdrive_data:
        logger.debug(f"Processing SalesDrive data: {salesdrive_data}")
        total_orders = salesdrive_data.get('total_orders', 0)
        real_orders = salesdrive_data.get('real_orders', 0)
        pending_orders = salesdrive_data.get('pending_orders', 0)
        sources = salesdrive_data.get('sources', {})
        
        insights.append(f"📋 Всього замовлень: {total_orders} (реальні: {real_orders}, в обробці: {pending_orders})")
        
        if sources:
            top_source = max(sources.items(), key=lambda x: x[1])
            insights.append(f"🎯 Найпопулярніше джерело: {top_source[0]} ({top_source[1]} замовлень)")
        
        # Generate recommendations based on conversion
        if total_orders > 0:
            conversion_rate = (real_orders / total_orders) * 100
            if conversion_rate < 50:
                recommendations.append("📞 Низька конверсія обробки замовлень. Покращте роботу з клієнтами")
    
    # Analyze Clarity data
    if clarity_data:
        logger.debug(f"Processing Clarity data: {clarity_data}")
        traffic_data = clarity_data.get('traffic', {})
        clicks_data = clarity_data.get('clicks', {})
        scrolls_data = clarity_data.get('scrolls', {})
        
        if traffic_data:
            insights.append("🌐 Дані трафіку з Clarity отримано")
        if clicks_data:
            insights.append("👆 Дані кліків з Clarity отримано")
        if scrolls_data:
            insights.append("📜 Дані прокрутки з Clarity отримано")
            
        # Basic recommendations based on data availability
        if traffic_data or clicks_data or scrolls_data:
            recommendations.append("📈 Використовуйте дані Clarity для оптимізації UX сайту")
    
    # Default messages if no data
    if not insights:
        insights.append("📊 Дані для аналізу відсутні")
    
    if not recommendations:
        recommendations.append("💡 Збирайте більше даних для персоналізованих рекомендацій")
    
    insights_text = "\n".join(insights)
    recommendations_text = "\n".join(recommendations)
    
    logger.info("Insights generated successfully")
    return insights_text, recommendations_text