from flask import Flask, request, jsonify
import logging
import os
import traceback

app = Flask(__name__)

# Рекомендовано зберігати токен у змінній оточення
SALES_DRIVE_TOKEN = os.getenv("SALESDRIVE_WEBHOOK_TOKEN", "674ededa16...")

@app.route("/webhooks/salesdrive", methods=["POST"])
def salesdrive_webhook():
    token = request.args.get("token")
    if token != SALES_DRIVE_TOKEN:
        print(f"[WEBHOOK] Wrong token! Got: {token}")
        return "Forbidden", 403

    try:
        payload = request.get_json(force=True)
        print("[WEBHOOK] Payload:", payload)
        # Тут твоя логіка: обробка та збереження payload у БД
        # Наприклад: збереження у таблицю, надсилання у Telegram тощо
        # ...
        return jsonify({"status": "ok"})
    except Exception as e:
        logging.error("webhook_store_failed")
        print(f"[WEBHOOK] Error: {e}")
        print(traceback.format_exc())
        return "fail", 500

# Якщо потрібно, підключи цей blueprint у основний app, або просто імпортуй функцію
