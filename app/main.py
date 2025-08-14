import os
import json
import logging
from decimal import Decimal
from dotenv import load_dotenv
from flask import Flask, jsonify, request, Response
from .logging_conf import configure_logging
from .telegram import Telegram
from .db import migrate, get_session
from .reporting_ecom import aggregate_finance
from sqlalchemy import text
from datetime import date

load_dotenv()
configure_logging()
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change")

try:
    migrate()
except Exception:
    logging.exception("migrate_fail")

@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok"})

@app.get("/debug/last-orders")
def last_orders():
    s = get_session()
    rows = s.execute(text(
        "SELECT id,created_at,order_id,amount_uah,brand,utm_campaign,status,shipped_at FROM orders ORDER BY id DESC LIMIT 10"
    )).mappings().all()
    return jsonify(list(rows))

@app.post("/webhook/salesdrive")
def webhook_salesdrive():
    p = request.get_json(silent=True) or {}
    try:
        s = get_session()
        order_id = str(p.get("id") or p.get("order_id") or "")
        status = str(p.get("status") or p.get("order_status") or p.get("state") or "")
        shipped = p.get("shipped_at") or p.get("delivery_date") or p.get("sent_at")
        def amount_of(pp):
            for keys in (
                ("total_uah",), ("amount_uah",), ("grand_total_uah",),
                ("total",), ("amount",), ("order", "amount")
            ):
                node = pp; ok = True
                for k in keys:
                    if isinstance(node, dict) and k in node:
                        node = node[k]
                    else:
                        ok = False; break
                if ok:
                    try: return Decimal(str(node))
                    except: pass
            return None
        brand = p.get("brand") or p.get("vendor") or p.get("manufacturer") or "Mamulya"
        source = p.get("utm_source") or (p.get("order") or {}).get("utm_source") or "unknown"
        camp = p.get("utm_campaign") or (p.get("order") or {}).get("utm_campaign") or "unknown"
        amt = amount_of(p)
        s.execute(text("INSERT INTO salesdrive_events(payload) VALUES(:p)"), {"p": json.dumps(p)})
        if amt is not None:
            if isinstance(shipped, (int, float)):
                s.execute(text(
                    "INSERT INTO orders(order_id,amount_uah,brand,utm_campaign,status,shipped_at) VALUES(:o,:a,:b,:c,:s,to_timestamp(:t))"
                ), {"o": order_id, "a": amt, "b": brand, "c": camp, "s": status, "t": shipped})
            else:
                s.execute(text(
                    "INSERT INTO orders(order_id,amount_uah,brand,utm_campaign,status,shipped_at) VALUES(:o,:a,:b,:c,:s,:t)"
                ), {"o": order_id, "a": amt, "b": brand, "c": camp, "s": status, "t": shipped})
        s.commit()
        try:
            msg = (
                f"🧾 <b>Нова подія із SalesDrive</b>\n"
                f"ID: <code>{order_id}</code>\n"
                f"Сума: <b>{int(amt) if amt is not None else '—'}</b>\n"
                f"utm_source: {source}\n"
                f"utm_campaign: {camp}"
            )
            Telegram().send(msg)
        except Exception:
            logging.exception("tg_notify_failed")
        return ("ok", 200)
    except Exception:
        logging.exception("webhook_store_failed")
        return ("error", 500)

@app.post("/webhooks/salesdrive")
def webhooks_salesdrive():
    # Перевірка токена
    token = request.args.get("token")
    expected_token = os.getenv("SALESDRIVE_WEBHOOK_TOKEN", "674ededa16...")
    if token != expected_token:
        print(f"[WEBHOOK] Wrong token! Got: {token}")
        return "Forbidden", 403

    p = request.get_json(silent=True) or {}
    try:
        s = get_session()
        order_id = str(p.get("id") or p.get("order_id") or "")
        status = str(p.get("status") or p.get("order_status") or p.get("state") or "")
        shipped = p.get("shipped_at") or p.get("delivery_date") or p.get("sent_at")
        def amount_of(pp):
            for keys in (
                ("total_uah",), ("amount_uah",), ("grand_total_uah",),
                ("total",), ("amount",), ("order", "amount")
            ):
                node = pp; ok = True
                for k in keys:
                    if isinstance(node, dict) and k in node:
                        node = node[k]
                    else:
                        ok = False; break
                if ok:
                    try: return Decimal(str(node))
                    except: pass
            return None
        brand = p.get("brand") or p.get("vendor") or p.get("manufacturer") or "Mamulya"
        source = p.get("utm_source") or (p.get("order") or {}).get("utm_source") or "unknown"
        camp = p.get("utm_campaign") or (p.get("order") or {}).get("utm_campaign") or "unknown"
        amt = amount_of(p)
        s.execute(text("INSERT INTO salesdrive_events(payload) VALUES(:p)"), {"p": json.dumps(p)})
        if amt is not None:
            if isinstance(shipped, (int, float)):
                s.execute(text(
                    "INSERT INTO orders(order_id,amount_uah,brand,utm_campaign,status,shipped_at) VALUES(:o,:a,:b,:c,:s,to_timestamp(:t))"
                ), {"o": order_id, "a": amt, "b": brand, "c": camp, "s": status, "t": shipped})
            else:
                s.execute(text(
                    "INSERT INTO orders(order_id,amount_uah,brand,utm_campaign,status,shipped_at) VALUES(:o,:a,:b,:c,:s,:t)"
                ), {"o": order_id, "a": amt, "b": brand, "c": camp, "s": status, "t": shipped})
        s.commit()
        try:
            msg = (
                f"🧾 <b>Нова подія із SalesDrive</b>\n"
                f"ID: <code>{order_id}</code>\n"
                f"Сума: <b>{int(amt) if amt is not None else '—'}</b>\n"
                f"utm_source: {source}\n"
                f"utm_campaign: {camp}"
            )
            Telegram().send(msg)
        except Exception:
            logging.exception("tg_notify_failed")
        return ("ok", 200)
    except Exception:
        logging.exception("webhook_store_failed")
        return ("error", 500)

@app.get("/report/preview")
def report_preview():
    from datetime import datetime as _dt
    day = request.args.get("date") or str(date.today())
    day_d = _dt.fromisoformat(day).date()
    f = aggregate_finance(day_d)
    ship = (f['real_sales_count'] / f['new_orders_count'] * 100) if f['new_orders_count'] else 0
    flag = "✅" if ship >= 60 else "⚠️" if ship >= 40 else "🚨"
    lines = [
        f"📊 Попередній звіт ({day_d})",
        f"Нові заявки: {f['new_orders_count']}",
        f"В процесі: {f['processing_orders_count']} на {f['processing_amount']:.0f} UAH",
        f"Реальні продажі: {f['real_sales_count']} на {f['real_sales_amount']:.0f} UAH (середній чек {f['real_avg_check']:.0f})",
        f"Конверсія обробки: {ship:.0f}% {flag}"
    ]
    return Response("\n".join(lines), mimetype="text/plain")

# Додаємо запуск Flask для локального тесту (для Render/Gunicorn це не потрібно, але локально стане у пригоді)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
