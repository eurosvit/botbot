import os, json
import logging
from decimal import Decimal as D
from datetime import datetime, timedelta, date
from sqlalchemy import text
from .db import get_session

logger = logging.getLogger(__name__)

REAL={s.lower() for s in ['shipped','completed','delivered','відвантажено','закрито','доставлено']}
PROC={s.lower() for s in ['processing','pending','in progress','в обробці','очікує підтвердження','очікує відправки']}

def _margins():
    logger.info("Loading margins from env")
    d=json.loads(os.getenv("BRAND_MARGINS_UAH","{}"))
    result = {str(k):D(str(v)) for k,v in d.items()}
    default = D(str(os.getenv("DEFAULT_MARGIN_UAH","0.3")))
    logger.debug(f"Margins: {result}, Default: {default}")
    return result, default

def _range(d:date, tz='Europe/Kyiv'):
    logger.info(f"Calculating time range for {d} in {tz}")
    from zoneinfo import ZoneInfo
    s=datetime.combine(d, datetime.min.time()).replace(tzinfo=ZoneInfo(tz))
    e=s+timedelta(days=1)
    logger.debug(f"Start: {s}, End: {e}")
    return s, e

def aggregate_finance(day:date):
    logger.info(f"Start aggregate_finance for {day}")
    margins,defm=_margins()
    s,e=_range(day)
    sess=get_session()
    logger.info("Querying ad_stats")
    row=sess.execute(text("SELECT COALESCE(SUM(cost),0), COALESCE(SUM(clicks),0), COALESCE(SUM(impressions),0) FROM ad_stats WHERE stat_date=:d"),{"d":day}).first()
    logger.debug(f"Ad stats row: {row}")
    ad=D(str(row[0] or 0)); clicks=int(row[1] or 0); imp=int(row[2] or 0)
    logger.info("Querying new orders")
    new=sess.execute(text("SELECT amount_uah, brand, utm_campaign, COALESCE(status,'') FROM orders WHERE created_at>=:s AND created_at<:e"),{"s":s,"e":e}).fetchall()
    logger.debug(f"New orders: {len(new)} found")
    proc_c=0; proc_a=D("0")
    for amt, br, camp, st in new:
        if str(st or '').lower() in PROC: proc_c+=1; proc_a+=D(str(amt or 0))
    logger.info("Querying real sales")
    real=sess.execute(text("SELECT amount_uah, brand, utm_campaign, COALESCE(status,''), shipped_at FROM orders WHERE shipped_at>=:s AND shipped_at<:e"),{"s":s,"e":e}).fetchall()
    logger.debug(f"Real sales: {len(real)} found")
    rc=0; rs=D("0"); gp=D("0"); ads_c=0
    for amt, br, camp, st, shipped_at in real:
        if str(st or '').lower() in REAL:
            amt=D(str(amt or 0)); m=margins.get(str(br), defm); rs+=amt; gp+=amt*m; rc+=1
            if camp and camp.strip().lower()!="unknown": ads_c+=1
    avg=(rs/rc) if rc else D("0"); avgm=(gp/rs) if rs>0 else D("0"); mgr=rs*D("0.05"); net=gp-ad-mgr
    logger.info(f"Finished calculations: new={len(new)}, processing={proc_c}, real={rc}")
    logger.debug(f"Finance dict: new_orders_count={len(new)}, real_sales_amount={rs}, net_profit={net}")

    # === Запис у daily_reports ===
    sess.execute(
        text("""
            INSERT INTO daily_reports (
                day, orders_count, orders_ads_count, sales_total, avg_check, ad_cost, manager_cost, avg_margin, gross_profit, net_profit,
                processing_orders_count, processing_amount, real_sales_count, real_sales_amount, real_avg_check
            ) VALUES (
                :day, :orders_count, :orders_ads_count, :sales_total, :avg_check, :ad_cost, :manager_cost, :avg_margin, :gross_profit, :net_profit,
                :processing_orders_count, :processing_amount, :real_sales_count, :real_sales_amount, :real_avg_check
            )
            ON CONFLICT (day) DO UPDATE SET
                orders_count = EXCLUDED.orders_count,
                orders_ads_count = EXCLUDED.orders_ads_count,
                sales_total = EXCLUDED.sales_total,
                avg_check = EXCLUDED.avg_check,
                ad_cost = EXCLUDED.ad_cost,
                manager_cost = EXCLUDED.manager_cost,
                avg_margin = EXCLUDED.avg_margin,
                gross_profit = EXCLUDED.gross_profit,
                net_profit = EXCLUDED.net_profit,
                processing_orders_count = EXCLUDED.processing_orders_count,
                processing_amount = EXCLUDED.processing_amount,
                real_sales_count = EXCLUDED.real_sales_count,
                real_sales_amount = EXCLUDED.real_sales_amount,
                real_avg_check = EXCLUDED.real_avg_check
        """),
        {
            "day": day,
            "orders_count": len(new),
            "orders_ads_count": ads_c,
            "sales_total": rs,
            "avg_check": avg,
            "ad_cost": ad,
            "manager_cost": mgr,
            "avg_margin": avgm,
            "gross_profit": gp,
            "net_profit": net,
            "processing_orders_count": proc_c,
            "processing_amount": proc_a,
            "real_sales_count": rc,
            "real_sales_amount": rs,
            "real_avg_check": avg,
        }
    )
    sess.commit()

    return {
        "new_orders_count":len(new),
        "processing_orders_count":proc_c,
        "processing_amount":proc_a,
        "real_sales_count":rc,
        "real_sales_amount":rs,
        "real_avg_check":avg,
        "orders_ads_count":ads_c,
        "ad_cost":ad,
        "manager_cost":mgr,
        "avg_margin":avgm,
        "gross_profit":gp,
        "net_profit":net,
        "clicks":clicks,
        "impressions":imp
    }

def get_daily_ecom_report():
    """
    Wrapper для імпорту з main.py. Повертає фінансовий звіт за поточний день.
    """
    logger.info("Called get_daily_ecom_report")
    return aggregate_finance(date.today())
