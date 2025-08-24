from datetime import date, timedelta
from sqlalchemy import text
from app.db import get_session
import logging

logger = logging.getLogger(__name__)

def daterange(period):
    """
    Визначає діапазон дат на основі вибраного періоду.
    """
    t = date.today()
    if period == "week":
        return (t - timedelta(days=7), t)
    elif period == "month":
        return (t - timedelta(days=30), t)
    else:
        raise ValueError("Invalid period. Choose 'week' or 'month'.")

def generate_actionable_insights(ecom_data=None, salesdrive_data=None, clarity_data=None, google_ads_data=None):
    """
    Аналізує дані з різних джерел та генерує actionable insights і рекомендації.
    """
    logger.info("Starting actionable insights generation")
    
    insights = []
    recommendations = []
    
    # Аналіз e-commerce даних
    if ecom_data:
        logger.debug(f"Processing ecom data: {ecom_data}")
        
        # Основні метрики
        sales_amount = float(ecom_data.get('real_sales_amount', 0))
        sales_count = int(ecom_data.get('real_sales_count', 0))
        ad_cost = float(ecom_data.get('ad_cost', 0))
        net_profit = float(ecom_data.get('net_profit', 0))
        avg_check = float(ecom_data.get('real_avg_check', 0))
        
        insights.append(f"💰 Продажі: {sales_amount:.2f} грн ({sales_count} замовлень)")
        insights.append(f"💵 Середній чек: {avg_check:.2f} грн")
        insights.append(f"📊 Витрати на рекламу: {ad_cost:.2f} грн")
        insights.append(f"✅ Чистий прибуток: {net_profit:.2f} грн")
        
        # ROAS розрахунок
        if ad_cost > 0:
            roas = sales_amount / ad_cost
            insights.append(f"📈 ROAS: {roas:.2f}")
            
            if roas < 2:
                recommendations.append("⚠️ ROAS нижче 2.0 - оптимізуйте рекламні кампанії")
            elif roas > 5:
                recommendations.append("🚀 Відмінний ROAS - розгляньте збільшення бюджету")
        
        # Рентабельність
        if sales_amount > 0:
            profit_margin = (net_profit / sales_amount) * 100
            insights.append(f"📊 Рентабельність: {profit_margin:.1f}%")
            
            if profit_margin < 15:
                recommendations.append("💡 Рентабельність низька - перегляньте ціноутворення або зменште витрати")
    
    # Аналіз Google Ads даних
    if google_ads_data:
        logger.debug(f"Processing Google Ads data: {google_ads_data}")
        
        status = google_ads_data.get('status', 'unknown')
        if status == 'success':
            total_cost = google_ads_data.get('total_cost', 0)
            conversions_value = google_ads_data.get('total_conversions_value', 0)
            roas = google_ads_data.get('roas', 0)
            campaigns_count = google_ads_data.get('campaigns_analyzed', 0)
            
            insights.append(f"📱 Google Ads: ${total_cost:.2f} витрачено, ${conversions_value:.2f} отримано")
            insights.append(f"🎯 ROAS Google Ads: {roas:.2f} ({campaigns_count} кампаній)")
            
            if roas < 3:
                recommendations.append("🔍 Google Ads ROAS низький - проаналізуйте ключові слова та аудиторії")
            if total_cost > 100 and conversions_value == 0:
                recommendations.append("❌ Немає конверсій в Google Ads - перевірте налаштування відстеження")
                
        elif status == 'warning':
            insights.append("⚠️ Google Ads: не налаштовано або недоступно")
            recommendations.append("🔧 Налаштуйте інтеграцію з Google Ads для повного аналізу")
        else:
            insights.append("❌ Google Ads: помилка отримання даних")
            recommendations.append("🛠️ Перевірте налаштування Google Ads API")
    
    # Аналіз SalesDrive даних
    if salesdrive_data:
        logger.debug(f"Processing salesdrive data: {salesdrive_data}")
        
        total_orders = salesdrive_data.get('total_orders', 0)
        real_orders = salesdrive_data.get('real_orders', 0)
        pending_orders = salesdrive_data.get('pending_orders', 0)
        
        if total_orders > 0:
            conversion_rate = (real_orders / total_orders) * 100
            insights.append(f"🎯 Конверсія замовлень: {conversion_rate:.1f}%")
            
            if conversion_rate < 70:
                recommendations.append("📞 Покращіть роботу з обробки замовлень - багато замовлень не конвертуються")
            
            if pending_orders > real_orders * 0.5:
                recommendations.append("⏰ Багато замовлень в обробці - пришвидшіть процес підтвердження")
    
    # Аналіз Clarity даних
    if clarity_data:
        logger.debug(f"Processing clarity data: {clarity_data}")
        
        # Загальна поведінка користувачів
        insights.append("🖱️ Аналіз поведінки користувачів (Clarity):")
        
        # Додаємо рекомендації базові
        recommendations.extend([
            "🔍 Проаналізуйте топ-сторінки з високим exit rate",
            "🛒 Оптимізуйте популярні товари для кращої конверсії",
            "📱 Покращіть мобільну версію сайту",
            "⚡ Зменшіть кількість JS-помилок на сайті"
        ])
    
    # Загальні рекомендації
    recommendations.extend([
        "📈 Проведіть A/B тестування головної сторінки",
        "🎨 Оптимізуйте дизайн кнопок призову до дії",
        "📞 Налаштуйте чат-бота для швидкого зворотного зв'язку",
        "📊 Настройте додаткові event tracking для кращої аналітики"
    ])
    
    insights_text = "\n".join(insights)
    recommendations_text = "\n".join([f"• {rec}" for rec in recommendations])
    
    logger.info("Actionable insights generation completed")
    return insights_text, recommendations_text

def generate_period_insights(period):
    """
    Генерує підсумкові дані для заданого періоду (legacy function).
    """
    start_date, end_date = daterange(period)
    session = get_session()

    # Виконання SQL-запиту
    rows = session.execute(
        text(
            """
            SELECT day, real_sales_count, real_sales_amount, ad_cost, manager_cost, gross_profit, net_profit
            FROM daily_reports
            WHERE day >= :start_date AND day < :end_date
            ORDER BY day
            """
        ),
        {"start_date": start_date, "end_date": end_date},
    ).fetchall()

    # Якщо даних немає
    if not rows:
        return {"message": f"No data available for the {period} period."}

    # Розрахунки
    total_sales = sum(float(row.real_sales_amount) for row in rows)
    net_profit = sum(float(row.net_profit) for row in rows)
    ad_costs = sum(float(row.ad_cost) for row in rows)
    manager_costs = sum(float(row.manager_cost) for row in rows)

    # Формування підсумкових даних
    summary = {
        "period": f"{start_date} — {end_date}",
        "total_sales": total_sales,
        "net_profit": net_profit,
        "ad_costs": ad_costs,
        "manager_costs": manager_costs,
        "daily_data": [
            {
                "day": row.day,
                "sales_count": int(row.real_sales_count),
                "sales_amount": float(row.real_sales_amount),
                "net_profit": float(row.net_profit),
            }
            for row in rows
        ],
    }

    return summary
