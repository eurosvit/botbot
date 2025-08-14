import os
import logging
import requests

API = "https://api.telegram.org/bot{t}/{m}"

class Telegram:
    def __init__(self, token=None, chat_id=None):
        self.t = token or os.getenv("TG_BOT_TOKEN")
        self.c = chat_id or os.getenv("TG_CHAT_ID")
        print(f"[TG INIT] token: {self.t}, chat_id: {self.c}")
        if not self.t or not self.c:
            print("[TG ERROR] TG creds missing!")
            raise RuntimeError("TG creds missing")

    def send(self, text):
        print(f"[TG SEND] Sending message: '{text}'")
        try:
            url = API.format(t=self.t, m="sendMessage")
            payload = {"chat_id": self.c, "text": text, "parse_mode": "HTML"}
            print(f"[TG SEND] URL: {url}")
            print(f"[TG SEND] Payload: {payload}")
            r = requests.post(url, json=payload, timeout=15)
            print(f"[TG SEND] Response status: {r.status_code}")
            print(f"[TG SEND] Response text: {r.text}")
            r.raise_for_status()
            logging.info("{'event':'tg_ok'}")
            print("[TG SEND] Message sent OK!")
            return True
        except Exception as e:
            logging.exception("[TG SEND] tg_fail")
            print(f"[TG SEND] FAIL: {e}")
            return False

def send_report_to_telegram(text):
    """
    Wrapper function to send report text via Telegram.
    Uses environment variables for credentials.
    """
    try:
        tg = Telegram()
        return tg.send(text)
    except Exception as e:
        logging.error(f"Failed to send report to Telegram: {e}")
        return False
