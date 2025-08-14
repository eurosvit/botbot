
import os, logging, requests
API="https://api.telegram.org/bot{t}/{m}"
class Telegram:
    def __init__(self, token=None, chat_id=None):
        self.t=token or os.getenv("TG_BOT_TOKEN"); self.c=chat_id or os.getenv("TG_CHAT_ID")
        if not self.t or not self.c: raise RuntimeError("TG creds missing")
    def send(self, text):
        try:
            r=requests.post(API.format(t=self.t,m="sendMessage"), json={"chat_id":self.c,"text":text,"parse_mode":"HTML"}, timeout=15)
            r.raise_for_status(); logging.info("{'event':'tg_ok'}"); return True
        except Exception: logging.exception("tg_fail"); return False
