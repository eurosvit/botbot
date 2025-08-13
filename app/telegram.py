import os, logging, requests

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"

class Telegram:
    def __init__(self, token=None, chat_id=None, timeout=None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.timeout = int(os.getenv("TELEGRAM_TIMEOUT", "15")) if timeout is None else timeout
        assert self.token, "TELEGRAM_BOT_TOKEN is required"
        assert self.chat_id, "TELEGRAM_CHAT_ID is required"

    def send(self, text):
        url = TELEGRAM_API.format(token=self.token, method="sendMessage")
        try:
            r = requests.post(url, json={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}, timeout=self.timeout)
            r.raise_for_status()
            logging.info({"event":"telegram_ok","status":r.status_code})
            return True
        except Exception:
            logging.exception("telegram_send_failed")
            return False
