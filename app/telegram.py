import os, logging, requests
API="https://api.telegram.org/bot{t}/{m}"
class Telegram:
    def __init__(self, token=None, chat_id=None, timeout=None):
        self.t=token or os.getenv("TG_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
        self.c=chat_id or os.getenv("TG_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")
        self.timeout=int(os.getenv("TELEGRAM_TIMEOUT","15")) if timeout is None else timeout
        if not self.t or not self.c: raise RuntimeError("TG_BOT_TOKEN and TG_CHAT_ID required")
    def send(self, text:str)->bool:
        try:
            r=requests.post(API.format(t=self.t,m="sendMessage"), json={"chat_id":self.c,"text":text,"parse_mode":"HTML"}, timeout=self.timeout)
            r.raise_for_status(); logging.info({"event":"tg_ok"}); return True
        except Exception: logging.exception("tg_fail"); return False
