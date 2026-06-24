"""
Торговий рушій — зв'язує дані, стратегію, ризик та брокера в один цикл.

Один прохід (run_once):
  1. знімок капіталу + перевірка денного стоп-ліміту;
  2. для кожного символу:
     - тягнемо свічки (працюємо лише з ЗАКРИТИМИ свічками);
     - якщо є відкрита позиція — перевіряємо SL/TP та сигнал на вихід;
     - інакше, якщо є сигнал на купівлю і ліміти дозволяють — відкриваємо позицію
       з розміром за ризик-менеджментом.
"""
from __future__ import annotations

import logging
import time

from . import risk, store
from .broker import make_broker
from .config import TradingConfig
from .market import Market
from .notify import Notifier
from .strategy import make_strategy

log = logging.getLogger(__name__)


class Engine:
    def __init__(self, cfg: TradingConfig):
        cfg.validate()
        self.cfg = cfg
        self.market = Market(cfg)
        self.strategy = make_strategy(cfg)
        self.broker = make_broker(cfg, self.market)
        self.notifier = Notifier(cfg.notify)
        store.migrate_trading()

    # --- Один прохід циклу ---

    def run_once(self) -> None:
        mode = self.broker.mode
        equity = self.broker.equity()
        cash = self.broker.cash
        open_pos = store.open_positions(mode)
        by_symbol = {p["symbol"]: p for p in open_pos}
        store.snapshot_equity(mode, equity, cash, len(open_pos))

        pnl_today = store.realized_pnl_today(mode)
        entries_blocked = risk.daily_loss_exceeded(pnl_today, equity, self.cfg.max_daily_loss_pct)
        if entries_blocked:
            log.warning("Денний стоп-ліміт досягнуто (PnL=%.2f), нові входи заблоковано", pnl_today)

        for symbol in self.cfg.symbols:
            try:
                self._process_symbol(symbol, by_symbol.get(symbol), equity, cash,
                                     len(open_pos), entries_blocked)
            except Exception:
                log.exception("Помилка обробки символу %s", symbol)

    def _process_symbol(self, symbol, position, equity, cash, open_count, entries_blocked):
        candles = self.market.fetch_ohlcv(symbol)
        if len(candles) < self.cfg.ema_slow + 2:
            log.info("%s: замало свічок", symbol)
            return
        # Остання свічка може бути ще незакритою — відкидаємо для сигналу.
        closed = candles[:-1]
        signal = self.strategy.evaluate(closed)

        try:
            price = self.market.last_price(symbol)
        except Exception:
            price = signal.price

        if position:
            self._manage_open(position, signal, price)
            return

        if entries_blocked:
            return
        # Визначаємо бік входу: buy → long; sell → short (лише якщо дозволено).
        if signal.action == "buy":
            side = "long"
        elif signal.action == "sell" and self.cfg.allow_shorts:
            side = "short"
        else:
            return
        if open_count >= self.cfg.max_open_positions:
            log.info("%s: ліміт відкритих позицій (%d)", symbol, self.cfg.max_open_positions)
            return

        sl, tp = signal.levels(self.cfg, side)
        if sl is None:
            return
        qty = risk.position_size(equity, cash, price, sl, self.cfg.risk_per_trade,
                                 side=side, leverage=self.cfg.leverage)
        if qty <= 0:
            log.info("%s: нульовий розмір позиції (мало кешу/ризику)", symbol)
            return

        pos_id = self.broker.open(symbol, side, qty, price, sl, tp, signal.reason)
        if pos_id:
            emoji = "🟢" if side == "long" else "🔴"
            self.notifier.send(
                f"{emoji} <b>{'LONG' if side == 'long' else 'SHORT'}</b> {symbol}\n"
                f"Ціна: {price:.4f}\nК-сть: {qty:.6f}\n"
                f"SL: {sl:.4f}  TP: {tp:.4f}\n"
                f"Привід: {signal.reason}\nРежим: {self.broker.mode}"
            )

    def _manage_open(self, position, signal, price):
        side = position["side"]
        sl = float(position["stop_loss"]) if position["stop_loss"] is not None else None
        tp = float(position["take_profit"]) if position["take_profit"] is not None else None
        reason = None
        if side == "long":
            if sl is not None and price <= sl:
                reason = "стоп-лосс"
            elif tp is not None and price >= tp:
                reason = "тейк-профіт"
            elif signal.action == "sell":
                reason = f"сигнал на вихід ({signal.reason})"
        else:  # short
            if sl is not None and price >= sl:
                reason = "стоп-лосс"
            elif tp is not None and price <= tp:
                reason = "тейк-профіт"
            elif signal.action == "buy":
                reason = f"сигнал на вихід ({signal.reason})"

        if reason:
            res = self.broker.close(position, price, reason)
            emoji = "✅" if res["pnl"] >= 0 else "🔻"
            self.notifier.send(
                f"{emoji} <b>CLOSE {side.upper()}</b> {position['symbol']}\n"
                f"Ціна: {price:.4f}\n"
                f"PnL: {res['pnl']:.2f} ({res['pnl_pct']:.2f}%)\n"
                f"Причина: {reason}\nРежим: {self.broker.mode}"
            )

    # --- Безкінечний цикл ---

    def run_forever(self) -> None:
        log.info("Старт торгового циклу: режим=%s стратегія=%s біржа=%s символи=%s тф=%s",
                 self.cfg.mode, self.cfg.strategy, self.cfg.exchange, self.cfg.symbols, self.cfg.timeframe)
        self.notifier.send(
            f"🤖 Торговий бот запущено\nРежим: <b>{self.cfg.mode}</b>\n"
            f"Стратегія: {self.cfg.strategy}\n"
            f"Біржа: {self.cfg.exchange}\nПари: {', '.join(self.cfg.symbols)}\n"
            f"Таймфрейм: {self.cfg.timeframe}"
        )
        while True:
            try:
                self.run_once()
            except Exception:
                log.exception("Помилка в торговому циклі")
            time.sleep(self.cfg.poll_seconds)
