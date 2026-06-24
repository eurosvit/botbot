"""
Торгові стратегії (long-only, як типово для спот-крипти).

Усі стратегії повертають уніфікований Signal (buy/sell/hold) + ATR для
адаптивних SL/TP. Вибір стратегії — через TRADE_STRATEGY:

  ema_rsi    — тренд: EMA-кросовер + RSI-фільтр (за замовчуванням)
  macd       — тренд: кросовер лінії MACD та сигнальної
  bollinger  — повернення до середнього: купівля під нижньою смугою
  donchian   — пробій: купівля на пробитті N-періодного максимуму

Архітектура для швидкості: кожна стратегія вміє порахувати індикатори ОДИН раз
на всю серію (indicators) і визначити сигнал на конкретній свічці (signal_at).
Це дозволяє бектесту працювати за O(N) замість O(N²). Усі індикатори причинні
(значення на барі i залежить лише від даних до i), тож результат ідентичний
покроковому перерахунку. evaluate() — зручна обгортка для live-режиму.

Шари розділені: стратегія працює лише з цінами/свічками і не знає, на якій
біржі чи ринку торгує — тож ту саму стратегію легко застосувати деінде.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import indicators as ind
from .config import TradingConfig


@dataclass
class Signal:
    action: str                       # "buy" | "sell" | "hold"
    price: float                      # ціна останньої закритої свічки
    atr: float | None = None          # поточний ATR (для SL/TP)
    rsi: float | None = None
    reason: str = ""
    extra: dict = field(default_factory=dict)

    def levels(self, cfg: TradingConfig, side: str = "long") -> tuple[float | None, float | None]:
        """Рівні стоп-лосс / тейк-профіт на основі ATR для long або short."""
        if not self.atr:
            return None, None
        if side == "short":
            return self.price + cfg.atr_sl_mult * self.atr, self.price - cfg.atr_tp_mult * self.atr
        return self.price - cfg.atr_sl_mult * self.atr, self.price + cfg.atr_tp_mult * self.atr

    def sl_tp(self, cfg: TradingConfig) -> tuple[float | None, float | None]:
        """Сумісність: рівні для LONG-входу."""
        return self.levels(cfg, "long")


class BaseStrategy:
    name = "base"

    def __init__(self, cfg: TradingConfig):
        self.cfg = cfg

    def indicators(self, closes, highs, lows) -> dict:
        """Порахувати всі потрібні індикатори ОДИН раз на всю серію."""
        raise NotImplementedError

    def signal_at(self, i: int, closes, d: dict) -> Signal:
        """Визначити сигнал на свічці з індексом i за попередньо порахованими індикаторами."""
        raise NotImplementedError

    def evaluate(self, candles: list[list[float]]) -> Signal:
        closes, highs, lows = self._ohlc(candles)
        d = self.indicators(closes, highs, lows)
        return self.signal_at(len(closes) - 1, closes, d)

    @staticmethod
    def _ohlc(candles):
        closes = [c[4] for c in candles]
        highs = [c[2] for c in candles]
        lows = [c[3] for c in candles]
        return closes, highs, lows


class EmaRsiStrategy(BaseStrategy):
    """Тренд: бичий EMA-кросовер із фільтром перекупленості за RSI."""
    name = "ema_rsi"

    def indicators(self, closes, highs, lows):
        cfg = self.cfg
        return {
            "ef": ind.ema(closes, cfg.ema_fast),
            "es": ind.ema(closes, cfg.ema_slow),
            "rsi": ind.rsi(closes, cfg.rsi_period),
            "atr": ind.atr(highs, lows, closes, cfg.atr_period),
        }

    def signal_at(self, i, closes, d):
        cfg = self.cfg
        ef, es, r, a = d["ef"], d["es"], d["rsi"], d["atr"]
        sig = Signal("hold", closes[i], atr=a[i], rsi=r[i])
        if i < 1 or None in (ef[i], ef[i - 1], es[i], es[i - 1], r[i]):
            sig.reason = "недостатньо даних"
            return sig
        bull = ef[i - 1] <= es[i - 1] and ef[i] > es[i]
        bear = ef[i - 1] >= es[i - 1] and ef[i] < es[i]
        if bull and r[i] < cfg.rsi_overbought:
            sig.action, sig.reason = "buy", f"EMA-кросовер вгору, RSI={r[i]:.1f}"
        elif bull:
            sig.reason = f"кросовер, але RSI={r[i]:.1f} перекуплений — пропуск"
        elif bear:
            sig.action, sig.reason = "sell", f"EMA-кросовер вниз, RSI={r[i]:.1f}"
        else:
            sig.reason = f"без сигналу (RSI={r[i]:.1f})"
        return sig


class MacdStrategy(BaseStrategy):
    """Тренд: кросовер лінії MACD та сигнальної лінії."""
    name = "macd"

    def indicators(self, closes, highs, lows):
        cfg = self.cfg
        line, signal, _ = ind.macd(closes, cfg.macd_fast, cfg.macd_slow, cfg.macd_signal)
        return {"line": line, "signal": signal, "atr": ind.atr(highs, lows, closes, cfg.atr_period)}

    def signal_at(self, i, closes, d):
        line, signal, a = d["line"], d["signal"], d["atr"]
        sig = Signal("hold", closes[i], atr=a[i])
        if i < 1 or None in (line[i], line[i - 1], signal[i], signal[i - 1]):
            sig.reason = "недостатньо даних"
            return sig
        if line[i - 1] <= signal[i - 1] and line[i] > signal[i]:
            sig.action, sig.reason = "buy", "MACD перетнув сигнальну вгору"
        elif line[i - 1] >= signal[i - 1] and line[i] < signal[i]:
            sig.action, sig.reason = "sell", "MACD перетнув сигнальну вниз"
        else:
            sig.reason = "без сигналу"
        return sig


class BollingerStrategy(BaseStrategy):
    """Повернення до середнього: купівля під нижньою смугою, вихід на середній."""
    name = "bollinger"

    def indicators(self, closes, highs, lows):
        cfg = self.cfg
        mid, upper, lower = ind.bollinger(closes, cfg.bb_period, cfg.bb_std)
        return {"mid": mid, "upper": upper, "lower": lower,
                "rsi": ind.rsi(closes, cfg.rsi_period),
                "atr": ind.atr(highs, lows, closes, cfg.atr_period)}

    def signal_at(self, i, closes, d):
        mid, lower, r, a = d["mid"], d["lower"], d["rsi"], d["atr"]
        price = closes[i]
        sig = Signal("hold", price, atr=a[i], rsi=r[i])
        if None in (mid[i], lower[i]):
            sig.reason = "недостатньо даних"
            return sig
        if price < lower[i]:
            sig.action, sig.reason = "buy", "ціна нижче нижньої смуги Боллінджера"
        elif price > mid[i]:
            sig.action, sig.reason = "sell", "ціна повернулась до середньої"
        else:
            sig.reason = "у межах смуг"
        return sig


class DonchianStrategy(BaseStrategy):
    """Пробій: купівля на пробитті N-періодного максимуму, вихід — пробій мінімуму."""
    name = "donchian"

    def indicators(self, closes, highs, lows):
        cfg = self.cfg
        up, lo = ind.donchian(highs, lows, cfg.donchian_period)
        return {"up": up, "lo": lo, "atr": ind.atr(highs, lows, closes, cfg.atr_period)}

    def signal_at(self, i, closes, d):
        cfg = self.cfg
        up, lo, a = d["up"], d["lo"], d["atr"]
        price = closes[i]
        sig = Signal("hold", price, atr=a[i])
        if None in (up[i], lo[i]):
            sig.reason = "недостатньо даних"
            return sig
        if price > up[i]:
            sig.action, sig.reason = "buy", f"пробій максимуму {cfg.donchian_period}-періодів"
        elif price < lo[i]:
            sig.action, sig.reason = "sell", f"пробій мінімуму {cfg.donchian_period}-періодів"
        else:
            sig.reason = "у межах каналу"
        return sig


STRATEGIES: dict[str, type[BaseStrategy]] = {
    EmaRsiStrategy.name: EmaRsiStrategy,
    MacdStrategy.name: MacdStrategy,
    BollingerStrategy.name: BollingerStrategy,
    DonchianStrategy.name: DonchianStrategy,
}


def make_strategy(cfg: TradingConfig) -> BaseStrategy:
    name = (cfg.strategy or "ema_rsi").strip().lower()
    if name not in STRATEGIES:
        raise ValueError(f"Невідома стратегія '{name}'. Доступні: {', '.join(STRATEGIES)}")
    return STRATEGIES[name](cfg)


def warmup_bars(cfg: TradingConfig) -> int:
    """Скільки свічок потрібно «розігріву», щоб усі індикатори були визначені."""
    return max(cfg.ema_slow, cfg.rsi_period, cfg.atr_period, cfg.bb_period,
              cfg.donchian_period, cfg.macd_slow + cfg.macd_signal) + 2


# Зворотна сумісність: Strategy == стратегія за замовчуванням.
Strategy = EmaRsiStrategy
