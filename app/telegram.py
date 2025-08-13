import os, logging, requests
API = "https://api.telegram.org/bot{token}/{method}"
class Telegram:
    def __init__(self, token=None, chat_id=None, timeout=None):
        self.token = token or os.getenv("TG_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TG_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")
        self.timeout = int(os.getenv("TELEGRAM_TIMEOUT","15")) if timeout is None else timeout
        if not self.token or not self.chat_id:
            raise RuntimeError("TG_BOT_TOKEN and TG_CHAT_ID required")
    def send(self, text):
        try:
            r = requests.post(API.format(token=self.token, method="sendMessage"),
                              json={"chat_id": self.chat_id, "text": text, "parse_mode":"HTML"},
                              timeout=self.timeout)
            r.raise_for_status(); logging.info({"event":"tg_ok"}); return True
        except Exception:
            logging.exception("tg_fail"); return False
