import argparse
from datetime import date, timedelta
from sqlalchemy import text
from app.db import get_session

def daterange(period):
    t=date.today()
    return (t-timedelta(days=7), t) if period=="week" else (t-timedelta(days=30), t)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--period",choices=["week","month"],required=True)
    a=ap.parse_args(); s,e=daterange(a.period)
    sess=get_session()
    rows=sess.execute(text("""SELECT day, real_sales_count, real_sales_amount, ad_cost, manager_cost, gross_profit, net_profit
                             FROM daily_reports WHERE day>=:s AND day<:e ORDER BY day"""),{"s":s,"e":e}).fetchall()
    if not rows:
        print(f"No data for {a.period}."); return
    total=sum(float(r.real_sales_amount) for r in rows); net=sum(float(r.net_profit) for r in rows)
    ad=sum(float(r.ad_cost) for r in rows); mgr=sum(float(r.manager_cost) for r in rows)
    print(f"## {a.period.capitalize()} summary {s} — {e}")
    print(f"Реальні продажі: {total:.0f} UAH | Чистий: {net:.0f} UAH | Реклама: {ad:.0f} | Менеджер: {mgr:.0f}")
    for r in rows:
        print(f"- {r.day}: {int(r.real_sales_count)} шт. на {float(r.real_sales_amount):.0f} UAH, чистий {float(r.net_profit):.0f}")
if __name__=="__main__": main()
