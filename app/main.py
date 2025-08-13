import os, json, logging
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from .logging_conf import configure_logging
from .scheduler import create_scheduler
from .telegram import Telegram
from .db import init_db, get_session
from .utils import utcnow

load_dotenv()
configure_logging()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me")

# Initialize DB at startup and start scheduler (single worker)
try:
    init_db()
except Exception:
    logging.exception("db_init_failed")

_sched = create_scheduler(app)
_sched.start()

@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok", "time": utcnow().isoformat()})

@app.post("/webhook/salesdrive")
def webhook_salesdrive():
    payload = request.get_json(silent=True) or {}
    try:
        sess = get_session()
        sess.execute(
            "INSERT INTO salesdrive_events (payload) VALUES (:p)",
            {"p": json.dumps(payload)}
        )
        sess.commit()
        logging.info({"event":"salesdrive_saved"})
        Telegram().send("🧾 SalesDrive event received")
        return ("ok", 200)
    except Exception:
        logging.exception("salesdrive_store_failed")
        return ("error", 500)

@app.get("/trigger/telegram-test")
def trigger_telegram():
    ok = Telegram().send("✅ Telegram connectivity test")
    return jsonify({"sent": ok})

@app.get("/trigger/report-now")
def trigger_report_now():
    Telegram().send("🧭 Manual report trigger at: " + utcnow().isoformat())
    return jsonify({"status": "queued"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
