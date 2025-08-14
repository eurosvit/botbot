from datetime import date, timedelta
import os
import json
import sys
from sqlalchemy import text
from app.reporting_ecom import aggregate_finance
from app.telegram import Telegram
from app.db import migrate, get_session

def format_report(day, f):
    cur = os.getenv("CURRENCY", "UAH")
    shipped = (f['real_sales_count']/f['new_orders_count']*100) if f['new_orders_count'] else 0
    flag = "✅" if shipped >= 60 else "⚠️" if shipped >= 40 else "🚨"
    lines = [
        f"📊 Щоденний звіт ({day})",
        f"📦 Замовлення: нові {f['new_orders_count']}, в процесі {f['processing_orders_count']} на {f['processing_amount']:.0f} {cur}",
        f"🧾 Реальні продажі: {f['real_sales_count']} на {f['real_sales_amount']:.0f} {cur} | середній чек {f['real_avg_check']:.0f} {cur}",
        f"💸 Реклама: {f['ad_cost']:.0f} {cur} | 👩‍💼 Менеджер (5%): {f['manager_cost']:.0f} {cur}",
        f"📈 Маржа (середня): {float(f['avg_margin'])*100:.2f}% | Валовий: {f['gross_profit']:.0f} {cur}",
        f"✅ Чистий прибуток: {f['net_profit']:.0f} {cur}",
        f"🔁 Конверсія обробки: {shipped:.0f}% {flag}"
    ]
    return "\n".join(lines)

def main():
    print("=== START daily_report.py ===")
    # Logging env
    print("[ENV] TG_BOT_TOKEN:", os.getenv("TG_BOT_TOKEN"))
    print("[ENV] TG_CHAT_ID:", os.getenv("TG_CHAT_ID"))
    print("[ENV] DATABASE_URL:", os.getenv("DATABASE_URL"))
    print("[ENV] CURRENCY:", os.getenv("CURRENCY", "UAH"))
    try:
        migrate()
        print("[DB] Migration OK")
    except Exception as e:
        print("[ERROR] Migration failed:", e)
        sys.exit(1)
    day = date.today() - timedelta(days=1)
    print("[INFO] Aggregating data for day:", day)
    try:
        f = aggregate_finance(day)
        print("[INFO] Aggregated finance:", json.dumps(f, ensure_ascii=False, indent=2))
    except Exception as e:
        print("[ERROR] Aggregate finance failed:", e)
        sys.exit(1)
    try:
        s = get_session()
        print("[DB] Session acquired")
    except Exception as e:
        print("[ERROR] Get DB session failed:", e)
        sys.exit(1)
    try:
        s.execute(text("""
            INSERT INTO daily_reports(
                day, orders_count, orders_ads_count, sales_total, avg_check, ad_cost, manager_cost,
                avg_margin, gross_profit, net_profit, processing_orders_count, processing_amount,
                real_sales_count, real_sales_amount, real_avg_check, real_gross_profit, clarity_json
            )
            VALUES(:d,:oc,:oac,:st,:ac,:ad,:mgr,:am,:gp,:np,:pc,:pa,:rc,:ra,:rac,:rgp,:cj)
            ON CONFLICT(day) DO UPDATE SET
                orders_count=EXCLUDED.orders_count,
                orders_ads_count=EXCLUDED.orders_ads_count,
                sales_total=EXCLUDED.sales_total,
                avg_check=EXCLUDED.avg_check,
                ad_cost=EXCLUDED.ad_cost,
                manager_cost=EXCLUDED.manager_cost,
                avg_margin=EXCLUDED.avg_margin,
                gross_profit=EXCLUDED.gross_profit,
                net_profit=EXCLUDED.net_profit,
                processing_orders_count=EXCLUDED.processing_orders_count,
                processing_amount=EXCLUDED.processing_amount,
                real_sales_count=EXCLUDED.real_sales_count,
                real_sales_amount=EXCLUDED.real_sales_amount,
                real_avg_check=EXCLUDED.real_avg_check,
                real_gross_profit=EXCLUDED.real_gross_profit,
                clarity_json=EXCLUDED.clarity_json
        """), {
            "d": day,
            "oc": int(f.get('new_orders_count', 0)),
            "oac": int(f.get('orders_ads_count', 0)),
            "st": float(f.get('real_sales_amount', 0)),
            "ac": float(f.get('real_avg_check', 0)),
            "ad": float(f.get('ad_cost', 0)),
            "mgr": float(f.get('manager_cost', 0)),
            "am": float(f.get('avg_margin', 0)),
            "gp": float(f.get('gross_profit', 0)),
            "np": float(f.get('net_profit', 0)),
            "pc": int(f.get('processing_orders_count', 0)),
            "pa": float(f.get('processing_amount', 0)),
            "rc": int(f.get('real_sales_count', 0)),
            "ra": float(f.get('real_sales_amount', 0)),
            "rac": float(f.get('real_avg_check', 0)),
            "rgp": float(f.get('gross_profit', 0)),
            "cj": None
        })
        s.commit()
        print("[DB] daily_reports upserted")
    except Exception as e:
        print("[ERROR] DB upsert failed:", e)
        sys.exit(1)
    try:
        txt = format_report(day, f)
        print("[REPORT] Generated:\n", txt)
        Telegram().send(txt)
        print("[TG] Report sent successfully")
    except Exception as e:
        print("[ERROR] Telegram send failed:", e)
        sys.exit(1)
    print("=== END daily_report.py ===")

if __name__ == "__main__":
    main()
