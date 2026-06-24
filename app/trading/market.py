"""
Доступ до біржі через ccxt — єдиний уніфікований інтерфейс для 100+ бірж.
Тут зосереджено все, що стосується самої біржі: дані ринку та (для live)
виставлення реальних ордерів. Публічні дані (свічки/ціни) доступні без ключів,
тому paper-режим теж працює на справжніх ринкових цінах.
"""
from __future__ import annotations

import logging
import os

from .config import TradingConfig

log = logging.getLogger(__name__)


class Market:
    def __init__(self, cfg: TradingConfig):
        self.cfg = cfg
        self.client = self._build_client(cfg)

    @staticmethod
    def _build_client(cfg: TradingConfig):
        import ccxt  # імпорт усередині, щоб модуль не вимагав ccxt без потреби

        if not hasattr(ccxt, cfg.exchange):
            raise ValueError(f"ccxt не знає біржу '{cfg.exchange}'")
        klass = getattr(ccxt, cfg.exchange)

        params: dict = {"enableRateLimit": True,
                        "options": {"defaultType": cfg.market_type}}
        # Ключі потрібні лише для live; беремо за конвенцією EXCHANGE-агностично.
        api_key = os.getenv("TRADE_API_KEY")
        api_secret = os.getenv("TRADE_API_SECRET")
        if cfg.mode == "live":
            if not api_key or not api_secret:
                raise RuntimeError("LIVE-режим потребує TRADE_API_KEY та TRADE_API_SECRET")
            params["apiKey"] = api_key
            params["secret"] = api_secret
            api_password = os.getenv("TRADE_API_PASSWORD")  # деякі біржі (okx, kucoin)
            if api_password:
                params["password"] = api_password

        client = klass(params)
        if cfg.testnet and cfg.mode == "live":
            try:
                client.set_sandbox_mode(True)
                log.info("Sandbox/testnet увімкнено для %s", cfg.exchange)
            except Exception:
                log.warning("Біржа %s не підтримує sandbox через ccxt", cfg.exchange)
        return client

    # --- Ринкові дані (публічні) ---

    def fetch_ohlcv(self, symbol: str, limit: int | None = None) -> list[list[float]]:
        limit = limit or self.cfg.candle_limit
        return self.client.fetch_ohlcv(symbol, timeframe=self.cfg.timeframe, limit=limit)

    def last_price(self, symbol: str) -> float:
        return float(self.client.fetch_ticker(symbol)["last"])

    # --- Приватні операції (тільки live) ---

    def create_market_buy(self, symbol: str, amount: float, reduce_only: bool = False) -> dict:
        params = {"reduceOnly": True} if reduce_only else {}
        return self.client.create_order(symbol, "market", "buy", amount, None, params)

    def create_market_sell(self, symbol: str, amount: float, reduce_only: bool = False) -> dict:
        params = {"reduceOnly": True} if reduce_only else {}
        return self.client.create_order(symbol, "market", "sell", amount, None, params)

    def set_leverage(self, leverage: int, symbol: str) -> None:
        try:
            self.client.set_leverage(leverage, symbol)
        except Exception:
            log.warning("Не вдалося встановити плече %sx для %s", leverage, symbol)

    def free_balance(self, currency: str) -> float:
        bal = self.client.fetch_balance()
        return float(bal.get("free", {}).get(currency, 0.0) or 0.0)

    def amount_to_precision(self, symbol: str, amount: float) -> float:
        try:
            return float(self.client.amount_to_precision(symbol, amount))
        except Exception:
            return amount
