import os, json
from datetime import date, timedelta
from app.reporting_ecom import aggregate_finance
from app.db import migrate, get_session
from app.telegram import Telegram
from app.clarity import fetch_clarity_json

def fmt(day,f):
    cur=os.getenv("CURRENCY","UAH")
    rate=(f['real_sales_count']/f['new_orders_count']*100) if f['new_orders_count'] else 0
    flag="✅" if rate>=60 else "⚠️" if rate>=40 else "🚨"
    pflag="✅" if f['net_profit']>0 else "❌"
    return "\n".join([
        f"📊 Щоденний звіт ({day.strftime('%d %B %Y')})",
        f"📦 Нові {f['new_orders_count']} | В процесі {f['processing_orders_count']} на {f['processing_amount']:.0f} {cur}",
        f"🧾 Реальні {f['real_sales_count']} на {f['real_sales_amount']:.0f} {cur} | середній {f['real_avg_check']:.0f} {cur}",
        f"💸 Реклама {f['ad_cost']:.0f} {cur} | 👩‍💼 Менеджер 5% {f['manager_cost']:.0f} {cur}",
        f"📈 Маржа {float(f['avg_margin'])*100:.2f}% | Валовий {f['gross_profit']:.0f} {cur}",
        f"✅ Чистий прибуток {f['net_profit']:.0f} {cur} {pflag}",
        f"🔁 Конверсія обробки {rate:.0f}% {flag}",
        "", "🧭 Clarity: JSON збережено до БД (якщо доступний токен)."
    ])

def save(day,f,clarity):
    s=get_session()
    s.execute("""INSERT INTO daily_reports
       (day,orders_count,orders_ads_count,sales_total,avg_check,ad_cost,manager_cost,avg_margin,gross_profit,net_profit,
        processing_orders_count,processing_amount,real_sales_count,real_sales_amount,real_avg_check,real_gross_profit,clarity_json)
       VALUES(:d,:oc,:oac,:st,:ac,:ad,:mgr,:am,:gp,:np,:pc,:pa,:rc,:ra,:rav,:rg,:cj)
       ON CONFLICT(day) DO UPDATE SET
         orders_count=EXCLUDED.orders_count, orders_ads_count=EXCLUDED.orders_ads_count, sales_total=EXCLUDED.sales_total,
         avg_check=EXCLUDED.avg_check, ad_cost=EXCLUDED.ad_cost, manager_cost=EXCLUDED.manager_cost,
         avg_margin=EXCLUDED.avg_margin, gross_profit=EXCLUDED.gross_profit, net_profit=EXCLUDED.net_profit,
         processing_orders_count=EXCLUDED.processing_orders_count, processing_amount=EXCLUDED.processing_amount,
         real_sales_count=EXCLUDED.real_sales_count, real_sales_amount=EXCLUDED.real_sales_amount,
         real_avg_check=EXCLUDED.real_avg_check, real_gross_profit=EXCLUDED.real_gross_profit, clarity_json=EXCLUDED.clarity_json
    """,{"d":day,"oc":int(f["new_orders_count"]),"oac":int(f["orders_ads_count"]),"st":float(f["real_sales_amount"]),
          "ac":float(f["real_avg_check"]),"ad":float(f["ad_cost"]),"mgr":float(f["manager_cost"]),
          "am":float(f["avg_margin"]),"gp":float(f["gross_profit"]),"np":float(f["net_profit"]),
          "pc":int(f["processing_orders_count"]),"pa":float(f["processing_amount"]),
          "rc":int(f["real_sales_count"]),"ra":float(f["real_sales_amount"]),
          "rav":float(f["real_avg_check"]),"rg":float(f["gross_profit"]),"cj":json.dumps(clarity) if clarity else None})
    s.commit()

def main():
    migrate()
    day=date.today()-timedelta(days=1)
    f=aggregate_finance(day); clarity=fetch_clarity_json()
    txt=fmt(day,f); save(day,f,clarity); Telegram().send(txt); print(txt)

if __name__=="__main__": main()
