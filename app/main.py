import os, json, logging
from decimal import Decimal
from dotenv import load_dotenv
from flask import Flask, jsonify, request, Response
from .logging_conf import configure_logging
from .db import migrate, get_session
from .reporting_ecom import aggregate_finance
from datetime import date
load_dotenv(); configure_logging()
app=Flask(__name__); app.config["SECRET_KEY"]=os.getenv("SECRET_KEY","change-me")
try: migrate()
except Exception: logging.exception("migrate_fail")

@app.get("/healthz")
def healthz(): return jsonify({"ok":True})

@app.post("/webhook/salesdrive")
def webhook_salesdrive():
    p=request.get_json(silent=True) or {}
    try:
        s=get_session()
        order_id=str(p.get("id") or p.get("order_id") or "")
        status=str(p.get("status") or p.get("order_status") or p.get("state") or "")
        shipped_at=p.get("shipped_at") or p.get("delivery_date") or p.get("sent_at")
        def amount(pp):
            for path in (("total_uah",),("amount_uah",),("grand_total_uah",),("total",),("amount",),("grand_total",),("order","grand_total"),("order","amount")):
                n=pp
                for k in path:
                    n=n.get(k) if isinstance(n,dict) else None
                    if n is None: break
                if n is not None:
                    try: return Decimal(str(n))
                    except: pass
            return None
        brand=(p.get("brand") or p.get("vendor") or p.get("manufacturer") or "Mamulya")
        utm=p.get("utm_campaign") or (p.get("order") or {}).get("utm_campaign") or "unknown"
        amt=amount(p)
        s.execute("INSERT INTO salesdrive_events(payload) VALUES(:p)",{"p":json.dumps(p)})
        if amt is not None:
            if isinstance(shipped_at,(int,float)):
                s.execute("INSERT INTO orders(order_id,amount_uah,brand,utm_campaign,status,shipped_at) VALUES(:oid,:a,:b,:u,:st,to_timestamp(:ts))",
                          {"oid":order_id,"a":amt,"b":brand,"u":utm,"st":status,"ts":shipped_at})
            else:
                s.execute("INSERT INTO orders(order_id,amount_uah,brand,utm_campaign,status,shipped_at) VALUES(:oid,:a,:b,:u,:st,:ship)",
                          {"oid":order_id,"a":amt,"b":brand,"u":utm,"st":status,"ship":shipped_at})
        s.commit(); return ("ok",200)
    except Exception:
        logging.exception("webhook_fail"); return ("error",500)

@app.post("/ingest/google-ads")
def ingest_ads():
    d=request.get_json(silent=True) or {}
    if not d.get("stat_date") or not d.get("campaign"):
        return jsonify({"ok":False,"error":"stat_date & campaign required"}),400
    cost=Decimal(str(d.get("cost",0)))
    s=get_session()
    s.execute("""INSERT INTO ad_stats(stat_date,campaign,cost,currency,clicks,impressions)
               VALUES(:d,:c,:cost,'UAH',:clk,:imp)
               ON CONFLICT(stat_date,campaign) DO UPDATE
               SET cost=EXCLUDED.cost,currency=EXCLUDED.currency,clicks=EXCLUDED.clicks,impressions=EXCLUDED.impressions
               """,{"d":d["stat_date"],"c":d["campaign"],"cost":cost,"clk":int(d.get("clicks",0)),"imp":int(d.get("impressions",0))})
    s.commit(); return jsonify({"ok":True})

@app.get("/report/preview")
def preview():
    from datetime import datetime as _dt
    day=_dt.fromisoformat(request.args.get("date") or str(date.today())).date()
    f=aggregate_finance(day)
    shipped=(f['real_sales_count']/f['new_orders_count']*100) if f['new_orders_count'] else 0
    flag="✅" if shipped>=60 else "⚠️" if shipped>=40 else "🚨"
    lines=[f"📊 Попередній звіт ({day})",
           f"Нові: {f['new_orders_count']} | В процесі: {f['processing_orders_count']} на {f['processing_amount']:.0f} UAH",
           f"Реальні: {f['real_sales_count']} на {f['real_sales_amount']:.0f} UAH (середній {f['real_avg_check']:.0f})",
           f"Обробка: {shipped:.0f}% {flag} | Реклама {f['ad_cost']:.0f} | Менеджер {f['manager_cost']:.0f}",
           f"Маржа {float(f['avg_margin'])*100:.2f}% | Валовий {f['gross_profit']:.0f} | Чистий {f['net_profit']:.0f}"]
    return Response("\n".join(lines), mimetype="text/plain")
