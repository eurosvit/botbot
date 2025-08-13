import os, json
from decimal import Decimal as D
from datetime import datetime, timedelta, date
from sqlalchemy import text
from .db import get_session

REAL={s.lower() for s in ['Shipped','Completed','Delivered','Відвантажено','Закрито','Доставлено']}
PROC={s.lower() for s in ['Processing','Pending','In Progress','В обробці','Очікує підтвердження','Очікує відправки']}

def _margins():
    d=json.loads(os.getenv("BRAND_MARGINS_UAH","{}"))
    from decimal import Decimal as D
    return {str(k):D(str(v)) for k,v in d.items()}, D(str(os.getenv("DEFAULT_MARGIN_UAH","0.3")))

def _range(day: date, tz="Europe/Kyiv"):
    from zoneinfo import ZoneInfo
    s=datetime.combine(day, datetime.min.time()).replace(tzinfo=ZoneInfo(tz)); e=s+timedelta(days=1); return s,e

def aggregate_finance(day: date):
    margins, default=_margins()
    s,e=_range(day); sess=get_session()
    # ads
    row=sess.execute(text("SELECT COALESCE(SUM(cost),0), COALESCE(SUM(clicks),0), COALESCE(SUM(impressions),0) FROM ad_stats WHERE stat_date=:d"),{"d":day}).first()
    ad=D(str(row[0])) if row else D("0"); clicks=int(row[1] or 0) if row else 0; imps=int(row[2] or 0) if row else 0
    # new
    new_rows=sess.execute(text("SELECT amount_uah,brand,utm_campaign,COALESCE(status,'') FROM orders WHERE created_at>=:s AND created_at<:e"),{"s":s,"e":e}).fetchall()
    new_count=len(new_rows)
    proc_c=0; proc_amt=D("0")
    for amt,br,camp,st in new_rows:
        if str(st or "").lower() in PROC:
            proc_c+=1; proc_amt+=D(str(amt or 0))
    # real by shipped
    real_rows=sess.execute(text("SELECT amount_uah,brand,utm_campaign,COALESCE(status,''),shipped_at FROM orders WHERE shipped_at>=:s AND shipped_at<:e"),{"s":s,"e":e}).fetchall()
    real_amt=D("0"); real_c=0; gross=D("0"); ads_orders=0
    for amt,br,camp,st,sh in real_rows:
        if str(st or "").lower() in REAL:
            amt=D(str(amt or 0)); m=margins.get(str(br), default)
            real_amt+=amt; gross+=amt*m; real_c+=1
            if camp and camp.strip() and camp.strip().lower()!="unknown": ads_orders+=1
    avg_check=(real_amt/real_c) if real_c else D("0")
    avg_margin=((gross/real_amt) if real_amt>0 else D("0"))
    manager=real_amt*D("0.05")
    net=gross-ad-manager
    return {"new_orders_count":new_count,"processing_orders_count":proc_c,"processing_amount":proc_amt,
            "real_sales_count":real_c,"real_sales_amount":real_amt,"real_avg_check":avg_check,
            "orders_ads_count":ads_orders,"ad_cost":ad,"manager_cost":manager,"avg_margin":avg_margin,
            "gross_profit":gross,"net_profit":net,"clicks":clicks,"impressions":imps}
