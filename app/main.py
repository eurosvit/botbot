import os, json, logging
from decimal import Decimal
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from .logging_conf import configure_logging
from .scheduler import create_scheduler
from .telegram import Telegram
from .db import init_db, get_session
from .reporting_ecom import build_daily_message
from datetime import date

load_dotenv()
configure_logging()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me")

# Init DB & scheduler (можна не користуватись, якщо є Render Cron)
try:
    init_db()
except Exception:
    logging.exception("db_init_failed")

_sched = create_scheduler(app)
_sched.start()

@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok"})

@app.post("/webhook/salesdrive")
def webhook_salesdrive():
    payload = request.get_json(silent=True) or {}
    try:
        sess = get_session()
        sess.execute("INSERT INTO salesdrive_events (payload) VALUES (:p)", {"p": json.dumps(payload)})
        def guess_brand(it, order):
            for kk in ("brand","Brand","vendor","manufacturer"):
                v = (it or {}).get(kk) or (order or {}).get(kk)
                if v: return str(v)
            title = ((it or {}).get("title") or "").lower()
            if "znana" in title: return "Znana"
            if "plate" in title or "healthy" in title: return "HealthyPlate"
            if "pecs" in title: return "PECS"
            return "Mamulya"
        def get_campaign(p):
            for chain in (("utm_campaign",),("order","utm_campaign"),("data","utm_campaign")):
                node=p; ok=True
                for k in chain:
                    node = node.get(k) if isinstance(node, dict) else None
                    if node is None: ok=False; break
                if ok and node: return str(node)
            return "unknown"
        def iter_items(p):
            for chain in (("order","items"),("data","items"),("items",)):
                node=p; ok=True
                for k in chain:
                    node = node.get(k) if isinstance(node, dict) else None
                    if node is None: ok=False; break
                if ok and isinstance(node,list): return node, (p.get("order") or p.get("data") or {})
            return None, {}
        items, order_info = iter_items(payload)
        campaign = get_campaign(payload)
        wrote=False
        if items:
            for it in items:
                qty = Decimal(str(it.get("quantity", it.get("qty",1) or 1)))
                val = None
                for k in ("price_uah","priceUAH","price","unit_price","unitPrice"):
                    if it.get(k) is not None: val = Decimal(str(it[k]))*qty; break
                if val is None:
                    for k in ("subtotal_uah","subtotal","amount","line_total"):
                        if it.get(k) is not None: val = Decimal(str(it[k])); break
                if not val: continue
                brand = guess_brand(it, order_info)
                sess.execute(
                    "INSERT INTO orders (order_id, amount_uah, brand, utm_campaign) VALUES (:oid,:amt,:br,:cmp)",
                    {"oid": str(payload.get("id") or payload.get("order_id") or ""), "amt": val, "br": brand, "cmp": campaign}
                )
                wrote=True
        if not wrote:
            amt = None
            for k in ("total_uah","amount_uah","grand_total_uah","total","amount","grand_total"):
                if payload.get(k) is not None: amt = Decimal(str(payload[k])); break
            if amt:
                brand = guess_brand({}, payload.get("order") or payload.get("data") or {})
                sess.execute(
                    "INSERT INTO orders (order_id, amount_uah, brand, utm_campaign) VALUES (:oid,:amt,:br,:cmp)",
                    {"oid": str(payload.get("id") or payload.get("order_id") or ""), "amt": amt, "br": brand, "cmp": campaign}
                )
        sess.commit()
        return ("ok", 200)
    except Exception:
        logging.exception("salesdrive_store_failed")
        return ("error", 500)

@app.post("/ingest/google-ads")
def ingest_google_ads():
    data = request.get_json(silent=True) or {}
    if not data.get("stat_date") or not data.get("campaign"):
        return jsonify({"ok": False, "error": "stat_date & campaign required"}), 400
    cost = Decimal(str(data.get("cost", 0)))  # UAH only
    sess = get_session()
    sess.execute(
        """INSERT INTO ad_stats (stat_date, campaign, cost, currency, clicks, impressions)
               VALUES (:d,:c,:cost,'UAH',:clk,:imp)
               ON CONFLICT (stat_date, campaign) DO UPDATE
               SET cost=EXCLUDED.cost, currency=EXCLUDED.currency, clicks=EXCLUDED.clicks, impressions=EXCLUDED.impressions
        """,
        {"d": data["stat_date"], "c": data["campaign"], "cost": cost,
         "clk": int(data.get("clicks",0)), "imp": int(data.get("impressions",0))}
    )
    sess.commit()
    return jsonify({"ok": True})

@app.get("/trigger/ecom-report")
def trigger_ecom_report():
    Telegram().send(build_daily_message(date.today()))
    return jsonify({"status":"sent"})

@app.get("/report/preview")
def report_preview():
    return build_daily_message(date.today())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
