import logging

logger = logging.getLogger(__name__)

def generate_actionable_insights(ecom_data=None, salesdrive_data=None, clarity_data=None):
    """
    Generate actionable insights based on ecommerce, SalesDrive, and Clarity data.
    Returns insights text and recommendations text.
    """
    try:
        logger.info("Generating actionable insights")
        
        insights = []
        recommendations = []
        
        # Analyze ecommerce data
        if ecom_data:
            logger.debug("Processing ecommerce data for insights")
            insights.append("📊 Аналіз E-commerce:")
            
            # Add basic insights based on available data
            if isinstance(ecom_data, dict):
                if 'real_sales_count' in ecom_data:
                    insights.append(f"- Реальних продажів: {ecom_data.get('real_sales_count', 0)}")
                if 'real_sales_amount' in ecom_data:
                    insights.append(f"- Сума продажів: {ecom_data.get('real_sales_amount', 0):.2f} UAH")
                if 'net_profit' in ecom_data:
                    insights.append(f"- Чистий прибуток: {ecom_data.get('net_profit', 0):.2f} UAH")
        
        # Analyze SalesDrive data
        if salesdrive_data:
            logger.debug("Processing SalesDrive data for insights")
            insights.append("\n📞 Аналіз SalesDrive:")
            
            if isinstance(salesdrive_data, dict):
                if 'total_orders' in salesdrive_data:
                    insights.append(f"- Загальна кількість замовлень: {salesdrive_data.get('total_orders', 0)}")
                if 'real_orders' in salesdrive_data:
                    insights.append(f"- Виконаних замовлень: {salesdrive_data.get('real_orders', 0)}")
                if 'pending_orders' in salesdrive_data:
                    insights.append(f"- Замовлень в обробці: {salesdrive_data.get('pending_orders', 0)}")
        
        # Analyze Clarity data
        if clarity_data:
            logger.debug("Processing Clarity data for insights")
            insights.append("\n🔍 Аналіз Clarity:")
            
            if isinstance(clarity_data, dict):
                if 'traffic' in clarity_data and clarity_data['traffic']:
                    insights.append("- Дані про трафік отримано")
                if 'clicks' in clarity_data and clarity_data['clicks']:
                    insights.append("- Дані про кліки отримано")
                if 'scrolls' in clarity_data and clarity_data['scrolls']:
                    insights.append("- Дані про прокрутку отримано")
        
        # Generate recommendations
        recommendations.append("💡 Рекомендації:")
        recommendations.append("- Регулярно відстежуйте ключові метрики")
        recommendations.append("- Аналізуйте ефективність рекламних кампаній")
        recommendations.append("- Оптимізуйте конверсію на основі даних Clarity")
        
        insights_text = "\n".join(insights) if insights else "Дані для аналізу недоступні"
        recommendations_text = "\n".join(recommendations)
        
        logger.info("Actionable insights generated successfully")
        return insights_text, recommendations_text
        
    except Exception as e:
        logger.error(f"Error generating insights: {e}")
        logger.exception("Insights generation error details")
        return "Помилка при генерації інсайтів", "Не вдалося сформувати рекомендації"