"""
Торгова стратегія: EMA-кросовер з RSI-фільтром та ATR-рівнями.

Логіка (long-only, що типово для спот-крипти):
  * Вхід LONG, коли швидка EMA перетинає повільну знизу вгору (бичий кросовер)
    і RSI не в зоні перекупленості (фільтр від входу на піку).
  * Стоп-лосс і тейк-профіт рахуються від поточної волатильності (ATR),
    тож вони адаптивні до ринку, а не фіксовані відсотки.
  * Вихід — або по SL/TP (керує брокер), або по зворотному кросовері.

Стратегія свідомо проста і прозора: це база MVP, яку легко розширювати
(додати шорти, інші індикатори, мультистратегійність, ML-сигнали тощо).
"""
from __future__ import annotations

from dataclasses import dataclass

from . import indicators as ind
from .config import TradingConfig


@dataclass
class Signal:
    action: str                 # "buy" | "sell" | "hold"
    price: float                # ціна останньої закритої свічки
    atr: float | None           # поточний ATR (для SL/TP)
    rsi: float | None
    ema_fast: float | None
    ema_slow: float | None
    reason: str = ""

    def sl_tp(self, cfg: TradingConfig) -> tuple[float | None, float | None]:
        """Рівні стоп-лосс / тейк-профіт для LONG-входу на основі ATR."""
        if not self.atr:
            return None, None
        sl = self.price - cfg.atr_sl_mult * self.atr
        tp = self.price + cfg.atr_tp_mult * self.atr
        return sl, tp


class Strategy:
    def __init__(self, cfg: TradingConfig):
        self.cfg = cfg

    def evaluate(self, candles: list[list[float]]) -> Signal:
        """
        candles — список свічок ccxt: [timestamp, open, high, low, close, volume].
        Працюємо лише з закритими свічками (останню, можливо незакриту,
        викликач має відкидати — engine це робить).
        """
        closes = [c[4] for c in candles]
        highs = [c[2] for c in candles]
        lows = [c[3] for c in candles]
        price = closes[-1]

        ef = ind.ema(closes, self.cfg.ema_fast)
        es = ind.ema(closes, self.cfg.ema_slow)
        r = ind.rsi(closes, self.cfg.rsi_period)
        a = ind.atr(highs, lows, closes, self.cfg.atr_period)

        ef_now, ef_prev = ef[-1], ef[-2]
        es_now, es_prev = es[-1], es[-2]
        rsi_now = r[-1]
        atr_now = a[-1]

        base = Signal(
            action="hold", price=price, atr=atr_now, rsi=rsi_now,
            ema_fast=ef_now, ema_slow=es_now,
        )

        if None in (ef_now, ef_prev, es_now, es_prev, rsi_now):
            base.reason = "недостатньо даних для індикаторів"
            return base

        bull_cross = ef_prev <= es_prev and ef_now > es_now
        bear_cross = ef_prev >= es_prev and ef_now < es_now

        if bull_cross and rsi_now < self.cfg.rsi_overbought:
            base.action = "buy"
            base.reason = f"бичий EMA-кросовер, RSI={rsi_now:.1f}"
        elif bull_cross and rsi_now >= self.cfg.rsi_overbought:
            base.reason = f"кросовер є, але RSI={rsi_now:.1f} перекуплений — пропуск"
        elif bear_cross:
            base.action = "sell"
            base.reason = f"ведмежий EMA-кросовер, RSI={rsi_now:.1f}"
        else:
            base.reason = f"тренд без сигналу (RSI={rsi_now:.1f})"

        return base
