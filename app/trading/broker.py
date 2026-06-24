"""
Брокери виконання угод. Підтримують long і short, spot та swap (ф'ючерси) з плечем.

PaperBroker — симулює угоди на реальних цінах:
  * spot  — тримає віртуальний кеш, купує/продає актив (тільки long);
  * swap  — маржинальна модель: під позицію резервується margin = notional/leverage,
            на закритті повертається margin ± PnL (long і short).
LiveBroker  — виставляє реальні ринкові ордери через біржу (ccxt).

Обидва зберігають позиції в БД (store), тож стан переживає рестарти.
Інтерфейс однаковий, тож engine не знає, у якому режимі працює.
"""
from __future__ import annotations

import logging

from . import risk, store
from .config import TradingConfig
from .market import Market

log = logging.getLogger(__name__)


class PaperBroker:
    def __init__(self, cfg: TradingConfig, market: Market):
        self.cfg = cfg
        self.market = market
        self.mode = "paper"
        self.cash = cfg.paper_balance

    def _price(self, symbol: str, fallback: float) -> float:
        try:
            return self.market.last_price(symbol)
        except Exception:
            return fallback

    def equity(self) -> float:
        total = self.cash
        for p in store.open_positions(self.mode):
            qty = float(p["qty"])
            entry = float(p["entry_price"])
            side = p["side"]
            price = self._price(p["symbol"], entry)
            if self.cfg.market_type == "swap":
                margin = qty * entry / max(self.cfg.leverage, 1)
                total += margin + risk.pnl(side, entry, price, qty)
            else:  # spot long: ринкова вартість активу
                total += qty * price
        return total

    def open(self, symbol, side, qty, price, sl, tp, reason) -> int | None:
        if qty <= 0:
            return None
        if self.cfg.market_type == "swap":
            margin = qty * price / max(self.cfg.leverage, 1)
            if margin > self.cash:
                log.warning("paper open відхилено: margin=%.2f cash=%.2f", margin, self.cash)
                return None
            self.cash -= margin
        else:  # spot — лише long, повна вартість
            cost = qty * price
            if side != "long" or cost > self.cash:
                log.warning("paper open відхилено: side=%s cost=%.2f cash=%.2f", side, cost, self.cash)
                return None
            self.cash -= cost
        pos_id = store.open_position({
            "mode": self.mode, "exchange": self.cfg.exchange, "symbol": symbol,
            "side": side, "qty": qty, "entry_price": price,
            "stop_loss": sl, "take_profit": tp, "reason_open": reason,
            "opened_at": _now(),
        })
        log.info("PAPER OPEN %s %s qty=%.6f @ %.2f (id=%s)", side, symbol, qty, price, pos_id)
        return pos_id

    def close(self, pos, price, reason) -> dict:
        qty = float(pos["qty"])
        entry = float(pos["entry_price"])
        side = pos["side"]
        p = risk.pnl(side, entry, price, qty)
        if self.cfg.market_type == "swap":
            margin = qty * entry / max(self.cfg.leverage, 1)
            self.cash += margin + p
        else:  # spot long: повертаємо виручку
            self.cash += qty * price
        pnl_pct = (p / (qty * entry) * 100.0) if entry and qty else 0.0
        store.close_position(pos["id"], price, p, pnl_pct, reason)
        log.info("PAPER CLOSE %s %s qty=%.6f @ %.2f pnl=%.2f (%.2f%%)",
                 side, pos["symbol"], qty, price, p, pnl_pct)
        return {"pnl": p, "pnl_pct": pnl_pct}


class LiveBroker:
    def __init__(self, cfg: TradingConfig, market: Market):
        self.cfg = cfg
        self.market = market
        self.mode = "live"

    @property
    def cash(self) -> float:
        return self.market.free_balance(self.cfg.quote_currency)

    def equity(self) -> float:
        total = self.cash
        for p in store.open_positions(self.mode):
            qty = float(p["qty"])
            entry = float(p["entry_price"])
            try:
                price = self.market.last_price(p["symbol"])
            except Exception:
                price = entry
            if self.cfg.market_type == "swap":
                total += qty * entry / max(self.cfg.leverage, 1) + risk.pnl(p["side"], entry, price, qty)
            else:
                total += qty * price
        return total

    def open(self, symbol, side, qty, price, sl, tp, reason) -> int | None:
        qty = self.market.amount_to_precision(symbol, qty)
        if qty <= 0:
            return None
        if self.cfg.market_type == "swap":
            self.market.set_leverage(self.cfg.leverage, symbol)
        order = (self.market.create_market_buy(symbol, qty) if side == "long"
                 else self.market.create_market_sell(symbol, qty))
        fill = float(order.get("average") or order.get("price") or price)
        filled = float(order.get("filled") or qty)
        pos_id = store.open_position({
            "mode": self.mode, "exchange": self.cfg.exchange, "symbol": symbol,
            "side": side, "qty": filled, "entry_price": fill,
            "stop_loss": sl, "take_profit": tp, "reason_open": reason,
            "opened_at": _now(),
        })
        log.info("LIVE OPEN %s %s qty=%.6f @ %.2f (id=%s)", side, symbol, filled, fill, pos_id)
        return pos_id

    def close(self, pos, price, reason) -> dict:
        qty = float(pos["qty"])
        entry = float(pos["entry_price"])
        side = pos["side"]
        # закриття: протилежний бік (reduceOnly для ф'ючерсів)
        reduce_only = self.cfg.market_type == "swap"
        order = (self.market.create_market_sell(pos["symbol"], qty, reduce_only=reduce_only) if side == "long"
                 else self.market.create_market_buy(pos["symbol"], qty, reduce_only=reduce_only))
        fill = float(order.get("average") or order.get("price") or price)
        p = risk.pnl(side, entry, fill, qty)
        pnl_pct = (p / (qty * entry) * 100.0) if entry and qty else 0.0
        store.close_position(pos["id"], fill, p, pnl_pct, reason)
        log.info("LIVE CLOSE %s %s qty=%.6f @ %.2f pnl=%.2f (%.2f%%)",
                 side, pos["symbol"], qty, fill, p, pnl_pct)
        return {"pnl": p, "pnl_pct": pnl_pct}


def make_broker(cfg: TradingConfig, market: Market):
    if cfg.mode == "live":
        return LiveBroker(cfg, market)
    return PaperBroker(cfg, market)


def _now():
    from app.utils import utcnow
    return utcnow()
