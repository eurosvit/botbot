"""
Брокери виконання угод.

PaperBroker — симулює угоди на реальних ринкових цінах, тримає віртуальний кеш.
LiveBroker  — виставляє реальні ринкові ордери через біржу (ccxt).

Обидва зберігають позиції в БД (store), тож стан переживає рестарти.
Інтерфейс однаковий, тож engine не знає, у якому режимі працює.
"""
from __future__ import annotations

import logging

from . import store
from .config import TradingConfig
from .market import Market

log = logging.getLogger(__name__)


class PaperBroker:
    def __init__(self, cfg: TradingConfig, market: Market):
        self.cfg = cfg
        self.market = market
        self.mode = "paper"
        self.cash = cfg.paper_balance

    def equity(self) -> float:
        """Кеш + поточна ринкова вартість відкритих позицій."""
        total = self.cash
        for p in store.open_positions(self.mode):
            try:
                price = self.market.last_price(p["symbol"])
            except Exception:
                price = float(p["entry_price"])
            total += float(p["qty"]) * price
        return total

    def buy(self, symbol: str, qty: float, price: float, sl: float, tp: float, reason: str) -> int | None:
        cost = qty * price
        if qty <= 0 or cost > self.cash:
            log.warning("paper buy відхилено: qty=%s cost=%.2f cash=%.2f", qty, cost, self.cash)
            return None
        self.cash -= cost
        pos_id = store.open_position({
            "mode": self.mode, "exchange": self.cfg.exchange, "symbol": symbol,
            "side": "long", "qty": qty, "entry_price": price,
            "stop_loss": sl, "take_profit": tp, "reason_open": reason,
            "opened_at": _now(),
        })
        log.info("PAPER BUY %s qty=%.6f @ %.2f (id=%s)", symbol, qty, price, pos_id)
        return pos_id

    def sell(self, pos: dict, price: float, reason: str) -> dict:
        qty = float(pos["qty"])
        entry = float(pos["entry_price"])
        proceeds = qty * price
        self.cash += proceeds
        pnl = (price - entry) * qty
        pnl_pct = (price / entry - 1.0) * 100.0
        store.close_position(pos["id"], price, pnl, pnl_pct, reason)
        log.info("PAPER SELL %s qty=%.6f @ %.2f pnl=%.2f (%.2f%%)",
                 pos["symbol"], qty, price, pnl, pnl_pct)
        return {"pnl": pnl, "pnl_pct": pnl_pct}


class LiveBroker:
    def __init__(self, cfg: TradingConfig, market: Market):
        self.cfg = cfg
        self.market = market
        self.mode = "live"

    def equity(self) -> float:
        cash = self.market.free_balance(self.cfg.quote_currency)
        total = cash
        for p in store.open_positions(self.mode):
            try:
                price = self.market.last_price(p["symbol"])
            except Exception:
                price = float(p["entry_price"])
            total += float(p["qty"]) * price
        return total

    @property
    def cash(self) -> float:
        return self.market.free_balance(self.cfg.quote_currency)

    def buy(self, symbol: str, qty: float, price: float, sl: float, tp: float, reason: str) -> int | None:
        qty = self.market.amount_to_precision(symbol, qty)
        if qty <= 0:
            return None
        order = self.market.create_market_buy(symbol, qty)
        fill = float(order.get("average") or order.get("price") or price)
        filled = float(order.get("filled") or qty)
        pos_id = store.open_position({
            "mode": self.mode, "exchange": self.cfg.exchange, "symbol": symbol,
            "side": "long", "qty": filled, "entry_price": fill,
            "stop_loss": sl, "take_profit": tp, "reason_open": reason,
            "opened_at": _now(),
        })
        log.info("LIVE BUY %s qty=%.6f @ %.2f (id=%s)", symbol, filled, fill, pos_id)
        return pos_id

    def sell(self, pos: dict, price: float, reason: str) -> dict:
        qty = float(pos["qty"])
        entry = float(pos["entry_price"])
        order = self.market.create_market_sell(pos["symbol"], qty)
        fill = float(order.get("average") or order.get("price") or price)
        pnl = (fill - entry) * qty
        pnl_pct = (fill / entry - 1.0) * 100.0
        store.close_position(pos["id"], fill, pnl, pnl_pct, reason)
        log.info("LIVE SELL %s qty=%.6f @ %.2f pnl=%.2f (%.2f%%)",
                 pos["symbol"], qty, fill, pnl, pnl_pct)
        return {"pnl": pnl, "pnl_pct": pnl_pct}


def make_broker(cfg: TradingConfig, market: Market):
    if cfg.mode == "live":
        return LiveBroker(cfg, market)
    return PaperBroker(cfg, market)


def _now():
    from app.utils import utcnow
    return utcnow()
