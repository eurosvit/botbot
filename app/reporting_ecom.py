
import os, json
from decimal import Decimal as D
from datetime import datetime, timedelta, date
from sqlalchemy import text
from .db import get_session
REAL={s.lower() for s in ['shipped','completed','delivered','відвантажено','закрито','доставлено']}
PROC={s.lower() for s in ['processing','pending','in progress','в обробці','очікує підтвердження','очікує відправки']}
def _margins():
    d=json.loads(os.getenv("BRAND_MARGINS_UAH","{}"))
    return {str(k):D(str(v)) for k,v in d.items()}, D(str(os.getenv("DEFAULT_MARGIN_UAH","0.3")))
def _range(d:date, tz='Europe/Kyiv'):
    from zoneinfo import ZoneInfo
    s=datetime.combine(d, datetime.min.time()).replace(tzinfo=ZoneInfo(tz)); e=s+timedelta(days=1); return s,e
def aggregate_finance(day:date):
    margins,defm=_margins(); s,e=_range(day); sess=get_session()
    row=sess.execute(text("SELECT COALESCE(SUM(cost),0), COALESCE(SUM(clicks),0), COALESCE(SUM(impressions),0) FROM ad_stats WHERE stat_date=:d"),{"d":day}).first()
    ad=D(str(row[0] or 0)); clicks=int(row[1] or 0); imp=int(row[2] or 0)
    new=sess.execute(text("SELECT amount_uah, brand, utm_campaign, COALESCE(status,'') FROM orders WHERE created_at>=:s AND created_at<:e"),{"s":s,"e":e}).fetchall()
    proc_c=0; proc_a=D("0")
    for amt, br, camp, st in new:
        if str(st or '').lower() in PROC: proc_c+=1; proc_a+=D(str(amt or 0))
    real=sess.execute(text("SELECT amount_uah, brand, utm_campaign, COALESCE(status,''), shipped_at FROM orders WHERE shipped_at>=:s AND shipped_at<:e"),{"s":s,"e":e}).fetchall()
    rc=0; rs=D("0"); gp=D("0"); ads_c=0
    for amt, br, camp, st, shipped_at in real:
        if str(st or '').lower() in REAL:
            amt=D(str(amt or 0)); m=margins.get(str(br), defm); rs+=amt; gp+=amt*m; rc+=1
            if camp and camp.strip().lower()!="unknown": ads_c+=1
    avg=(rs/rc) if rc else D("0"); avgm=(gp/rs) if rs>0 else D("0"); mgr=rs*D("0.05"); net=gp-ad-mgr
    return {"new_orders_count":len(new),"processing_orders_count":proc_c,"processing_amount":proc_a,"real_sales_count":rc,"real_sales_amount":rs,"real_avg_check":avg,"orders_ads_count":ads_c,"ad_cost":ad,"manager_cost":mgr,"avg_margin":avgm,"gross_profit":gp,"net_profit":net,"clicks":clicks,"impressions":imp}
