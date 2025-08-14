from datetime import date, timedelta

def format_daily_report(data):
    """
    Форматування щоденного звіту на основі даних.
    """
    report_date = (date.today() - timedelta(days=1)).strftime("%d %B")  # Дата за минулий день
    return f"""
📊 Mamulia — щоденний звіт ({report_date})

💰 Фінанси (CRM)

Реальні продажі: {data['real_sales_amount']} грн ({data['real_sales_count']} замовлень)

В процесі: {data['processing_amount']} грн ({data['processing_orders_count']} замовлення) 🕓

Скасовані: {data['cancelled_amount']} грн ({data['cancelled_orders_count']} замовлення) ❌

Реклама: {data['ad_cost']} грн

Менеджер: 5% = {data['manager_cost']} грн

Середня маржа: {data['avg_margin']}%

Чистий прибуток: {data['net_profit']} грн ✅
Формула: ({data['real_sales_amount']} × {data['avg_margin']/100}) − {data['ad_cost']} − {data['manager_cost']}

📦 Замовлення

Всього: {data['total_orders']}

По рекламі: {data['orders_ads_count']}

Середній чек: {data['avg_check']} грн

🧭 Clarity — поведінка користувачів
Аудиторія: {data['sessions']} сесія (-{data['bot_sessions']} ботів → {data['real_sessions']} реальних), {data['unique_users']} унік. користувачів
Пристрої: 📱 Mobile {data['mobile_percentage']}% • 💻 PC {data['pc_percentage']}%

Джерела / канали:
• Paid Search: {data['paid_search']} сесії
• Direct: {data['direct']} • Organic: {data['organic']} • Other: {data['other']} • Referral: {data['referral']}

🔥 Топ сторінки (сеанси / exit rate):
{data['top_pages']}

🛒 Популярні товари (інтерес / середній скрол):
{data['top_products']}

⚡ UX-інсайти:

Quick back clicks: {data['quick_back_clicks']}% сеансів ⚠️ (особливо з головної і {data['high_exit_page']})

Dead clicks: {data['dead_clicks']}% ✅

JS-помилки: {data['js_errors']} шт. ({data['js_error_details']})

🎯 Рекомендації (AI):
{data['recommendations']}
"""
