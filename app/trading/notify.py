"""
Сповіщення про угоди в Telegram. М'яко деградує: якщо ключі не задані
або сповіщення вимкнені — просто нічого не надсилає, не валить бота.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class Notifier:
    def __init__(self, enabled: bool = True):
        self.tg = None
        if not enabled:
            return
        try:
            from app.telegram import Telegram
            self.tg = Telegram()
        except Exception as e:
            log.warning("Telegram-сповіщення недоступні: %s", e)
            self.tg = None

    def send(self, text: str) -> None:
        if self.tg is None:
            return
        try:
            self.tg.send(text)
        except Exception:
            log.exception("Не вдалося надіслати сповіщення")
