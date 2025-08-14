import os, json, logging
from decimal import Decimal
from dotenv import load_dotenv
from flask import Flask, jsonify, request, Response
from .logging_conf import configure_logging
from .telegram import Telegram
from .db import migrate, get_session
from .reporting_ecom import aggregate_finance
from datetime import date
load_dotenv(); configure_logging()
app=Flask(__name__); app.config["SECRET_KEY"]=os.getenv("SECRET_KEY","change-me")
try: migrate()
except Exception: logging.exception("migrate_fail")
@app.get("/healthz")
def healthz(): return jsonify({"status":"ok"})
@app.post("/webhook/salesdrive")
def webhook_salesdrive():
    p=request.get_json(silent=True) or {}
    try:
        s=get_session()
        oid=str(p.get("id") or p.get("order_id") or "")
        st=str(p.get("status") or p.get("order_status") or p.get("state") or "")
        shipped=p.get("shipped_at") or p.get("delivery_date") or p.get("sent_at")
        def amt_of(pp):
            paths=(("total_uah",),("amount_uah",),("grand_total_uah",),("total",),("amount",),("order","amount"))
            for path in paths:
                node=pp
                for k in path:
                    if isinstance(node, dict) and k in node: node=node[k]
                    else: node=None; break
                if node is not None:
                    try: return Decimal(str(node))
                    except: pass
            return None
        brand=p.get("brand") or p.get("vendor") or p.get("manufacturer") or "Mamulya"
        camp=p.get("utm_campaign") or (p.get("order") or {}).get("utm_campaign") or "unknown"
        amount=amt_of(p)
        s.execute("INSERT INTO salesdrive_events(payload) VALUES (:p)", {"p": json.dumps(p)})
        if amount is not None:
            if isinstance(shipped,(int,float)):
                s.execute("INSERT INTO orders(order_id,amount_uah,brand,utm_campaign,status,shipped_at) VALUES (:o,:a,:b,:c,:s,to_timestamp(:t))",
                          {"o":oid,"a":amount,"b":brand,"c":camp,"s":st,"t":shipped})
            else:
                s.execute("INSERT INTO orders(order_id,amount_uah,brand,utm_campaign,status,shipped_at) VALUES (:o,:a,:b,:c,:s,:t)",
                          {"o":oid,"a":amount,"b":brand,"c":camp,"s":st,"t":shipped})
        s.commit(); return ("ok",200)
    except Exception:
        logging.exception("webhook_store_failed"); return ("error",500)
@app.post("/ingest/google-ads")
def ingest_google_ads():
    d=request.get_json(silent=True) or {}
    if not d.get("stat_date") or not d.get("campaign"): return jsonify({"ok":False,"error":"stat_date & campaign required"}),400
    cost=Decimal(str(d.get("cost",0))); s=get_session()
    s.execute("""INSERT INTO ad_stats(stat_date,campaign,cost,currency,clicks,impressions)
    VALUES(:d,:c,:cost,'UAH',:clk,:imp) ON CONFLICT(stat_date,campaign) DO UPDATE
    SET cost=EXCLUDED.cost,currency=EXCLUDED.currency,clicks=EXCLUDED.clicks,impressions=EXCLUDED.impressions""", 
             {"d":d["stat_date"],"c":d["campaign"],"cost":cost,"clk":int(d.get("clicks",0)),"imp":int(d.get("impressions",0))})
    s.commit(); return jsonify({"ok":True})
@app.get("/report/preview")
def report_preview():
    from datetime import datetime as _dt
    day=request.args.get("date") or str(date.today()); day_d=_dt.fromisoformat(day).date()
    f=aggregate_finance(day_d)
    ship=(f['real_sales_count']/f['new_orders_count']*100) if f['new_orders_count'] else 0
    flag="✅" if ship>=60 else "⚠️" if ship>=40 else "🚨"
    lines=[f"📊 Попередній звіт ({day_d})", f"Нові заявки: {f['new_orders_count']}", f"В процесі: {f['processing_orders_count']} на {f['processing_amount']:.0f} UAH",
           f"Реальні продажі: {f['real_sales_count']} на {f['real_sales_amount']:.0f} UAH (середній чек {f['real_avg_check']:.0f})",
           f"Конверсія обробки: {ship:.0f}% {flag}", f"Реклама: {f['ad_cost']:.0f} UAH | Менеджер (5%): {f['manager_cost']:.0f} UAH",
           f"Маржинальність (середня): {float(f['avg_margin'])*100:.2f}%", f"Валовий прибуток: {f['gross_profit']:.0f} UAH | Чистий: {f['net_profit']:.0f} UAH"]
    return Response("\n".join(lines), mimetype="text/plain")
