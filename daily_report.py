from datetime import date, timedelta
import os, json
from app.reporting_ecom import aggregate_finance
from app.telegram import Telegram
from app.db import migrate, get_session
from app.clarity import fetch_clarity_json
def format_report(day, f):
    cur=os.getenv("CURRENCY","UAH")
    shipped_rate=(f['real_sales_count']/f['new_orders_count']*100) if f['new_orders_count'] else 0
    shipped_flag="✅" if shipped_rate>=60 else "⚠️" if shipped_rate>=40 else "🚨"
    profit_flag="✅" if f['net_profit']>0 else "❌"
    lines=[f"📊 Щоденний звіт ({day.strftime('%d %B %Y')})", f"📦 Замовлення: нові {f['new_orders_count']}, в процесі {f['processing_orders_count']} на {f['processing_amount']:.0f} {cur}",
           f"🧾 Реальні продажі: {f['real_sales_count']} на {f['real_sales_amount']:.0f} {cur} | середній чек {f['real_avg_check']:.0f} {cur}",
           f"💸 Реклама: {f['ad_cost']:.0f} {cur} | 👩‍💼 Менеджер (5%): {f['manager_cost']:.0f} {cur}",
           f"📈 Маржа (середня): {float(f['avg_margin'])*100:.2f}% | Валовий: {f['gross_profit']:.0f} {cur}",
           f"✅ Чистий прибуток: {f['net_profit']:.0f} {cur} {profit_flag}",
           f"🔁 Конверсія обробки: {shipped_rate:.0f}% {shipped_flag} (частка відвантажених від нових)"]
    return "\n".join(lines)
def save_daily(day, f, clarity):
    s=get_session()
    s.execute("""INSERT INTO daily_reports(day,orders_count,orders_ads_count,sales_total,avg_check,ad_cost,manager_cost,avg_margin,gross_profit,net_profit,
        processing_orders_count,processing_amount,real_sales_count,real_sales_amount,real_avg_check,real_gross_profit,clarity_json)
        VALUES(:d,:oc,:oac,:st,:ac,:ad,:mgr,:am,:gp,:np,:pc,:pa,:rc,:ra,:rac,:rgp,:cj)
        ON CONFLICT(day) DO UPDATE SET orders_count=EXCLUDED.orders_count,orders_ads_count=EXCLUDED.orders_ads_count,
            sales_total=EXCLUDED.sales_total,avg_check=EXCLUDED.avg_check,ad_cost=EXCLUDED.ad_cost,manager_cost=EXCLUDED.manager_cost,
            avg_margin=EXCLUDED.avg_margin,gross_profit=EXCLUDED.gross_profit,net_profit=EXCLUDED.net_profit,
            processing_orders_count=EXCLUDED.processing_orders_count,processing_amount=EXCLUDED.processing_amount,
            real_sales_count=EXCLUDED.real_sales_count,real_sales_amount=EXCLUDED.real_sales_amount,real_avg_check=EXCLUDED.real_avg_check,
            real_gross_profit=EXCLUDED.real_gross_profit,clarity_json=EXCLUDED.clarity_json""", 
        {"d":day,"oc":int(f['new_orders_count']),"oac":int(f['orders_ads_count']),"st":float(f['real_sales_amount']),
         "ac":float(f['real_avg_check']),"ad":float(f['ad_cost']),"mgr":float(f['manager_cost']),"am":float(f['avg_margin']),
         "gp":float(f['gross_profit']),"np":float(f['net_profit']),"pc":int(f['processing_orders_count']),"pa":float(f['processing_amount']),
         "rc":int(f['real_sales_count']),"ra":float(f['real_sales_amount']),"rac":float(f['real_avg_check']),"rgp":float(f['gross_profit']),
         "cj":json.dumps(clarity) if clarity else None}); s.commit()
def main():
    migrate(); day=date.today()-timedelta(days=1)
    f=aggregate_finance(day); clarity=fetch_clarity_json(); txt=format_report(day,f); save_daily(day,f,clarity); Telegram().send(txt); print(txt)
if __name__=="__main__": main()
