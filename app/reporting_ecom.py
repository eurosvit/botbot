import os, json
from decimal import Decimal as D
from datetime import datetime, timedelta, date
from sqlalchemy import text
from .db import get_session

REAL={s.lower() for s in ['Shipped','Completed','Delivered','Відвантажено','Закрито','Доставлено']}
PROC={s.lower() for s in ['Processing','Pending','In Progress','В обробці','Очікує підтвердження','Очікує відправки']}

def _margins():
    d=json.loads(os.getenv("BRAND_MARGINS_UAH","{}"))
    return {str(k): D(str(v)) for k,v in d.items()}, D(str(os.getenv("DEFAULT_MARGIN_UAH","0.3")))

def _range(day: date, tz="Europe/Kyiv"):
    from zoneinfo import ZoneInfo
    s=datetime.combine(day, datetime.min.time()).replace(tzinfo=ZoneInfo(tz)); e=s+timedelta(days=1); return s,e

def aggregate_finance(day:date):
    margins,defm=_margins(); s,e=_range(day); sess=get_session()
    row=sess.execute(text("SELECT COALESCE(SUM(cost),0), COALESCE(SUM(clicks),0), COALESCE(SUM(impressions),0) FROM ad_stats WHERE stat_date=:d"),{"d":day}).first()
    ad=D(str(row[0] or 0)); clicks=int(row[1] or 0); imp=int(row[2] or 0)
    new=sess.execute(text("SELECT amount_uah, brand, utm_campaign, COALESCE(status,'') FROM orders WHERE created_at>=:s AND created_at<:e"),{"s":s,"e":e}).fetchall()
    new_cnt=len(new); proc_cnt=0; proc_amt=D("0")
    for amt, br, camp, st in new:
        if (st or '').lower() in PROC: proc_cnt+=1; proc_amt+=D(str(amt or 0))
    real=sess.execute(text("SELECT amount_uah, brand, utm_campaign, COALESCE(status,''), shipped_at FROM orders WHERE shipped_at>=:s AND shipped_at<:e"),{"s":s,"e":e}).fetchall()
    rs=D("0"); rc=0; gross=D("0"); ads_c=0
    for amt, br, camp, st, shipped_at in real:
        if (st or '').lower() in REAL:
            amt=D(str(amt or 0)); m=margins.get(str(br), defm)
            rs+=amt; gross+=amt*m; rc+=1
            if camp and camp.strip() and camp.strip().lower()!='unknown': ads_c+=1
    avg=(rs/rc) if rc else D("0"); avgm=(gross/rs) if rs>0 else D("0"); mgr=rs*D("0.05"); net=gross-ad-mgr
    return {"new_orders_count":new_cnt,"processing_orders_count":proc_cnt,"processing_amount":proc_amt,
            "real_sales_count":rc,"real_sales_amount":rs,"real_avg_check":avg,"orders_ads_count":ads_c,
            "ad_cost":ad,"manager_cost":mgr,"avg_margin":avgm,"gross_profit":gross,"net_profit":net,
            "clicks":clicks,"impressions":imp}
