"""
Торгові стратегії (long-only, як типово для спот-крипти).

Усі стратегії повертають уніфікований Signal (buy/sell/hold) + ATR для
адаптивних SL/TP. Вибір стратегії — через TRADE_STRATEGY:

  ema_rsi    — тренд: EMA-кросовер + RSI-фільтр (за замовчуванням)
  macd       — тренд: кросовер лінії MACD та сигнальної
  bollinger  — повернення до середнього: купівля під нижньою смугою
  donchian   — пробій: купівля на пробитті N-періодного максимуму

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

    def evaluate(self, candles: list[list[float]]) -> Signal:
        raise NotImplementedError

    @staticmethod
    def _ohlc(candles):
        closes = [c[4] for c in candles]
        highs = [c[2] for c in candles]
        lows = [c[3] for c in candles]
        return closes, highs, lows


class EmaRsiStrategy(BaseStrategy):
    """Тренд: бичий EMA-кросовер із фільтром перекупленості за RSI."""
    name = "ema_rsi"

    def evaluate(self, candles):
        cfg = self.cfg
        closes, highs, lows = self._ohlc(candles)
        ef = ind.ema(closes, cfg.ema_fast)
        es = ind.ema(closes, cfg.ema_slow)
        r = ind.rsi(closes, cfg.rsi_period)
        a = ind.atr(highs, lows, closes, cfg.atr_period)
        sig = Signal("hold", closes[-1], atr=a[-1], rsi=r[-1])
        if None in (ef[-1], ef[-2], es[-1], es[-2], r[-1]):
            sig.reason = "недостатньо даних"
            return sig
        bull = ef[-2] <= es[-2] and ef[-1] > es[-1]
        bear = ef[-2] >= es[-2] and ef[-1] < es[-1]
        if bull and r[-1] < cfg.rsi_overbought:
            sig.action, sig.reason = "buy", f"EMA-кросовер вгору, RSI={r[-1]:.1f}"
        elif bull:
            sig.reason = f"кросовер, але RSI={r[-1]:.1f} перекуплений — пропуск"
        elif bear:
            sig.action, sig.reason = "sell", f"EMA-кросовер вниз, RSI={r[-1]:.1f}"
        else:
            sig.reason = f"без сигналу (RSI={r[-1]:.1f})"
        return sig


class MacdStrategy(BaseStrategy):
    """Тренд: кросовер лінії MACD та сигнальної лінії."""
    name = "macd"

    def evaluate(self, candles):
        cfg = self.cfg
        closes, highs, lows = self._ohlc(candles)
        line, signal, _ = ind.macd(closes, cfg.macd_fast, cfg.macd_slow, cfg.macd_signal)
        a = ind.atr(highs, lows, closes, cfg.atr_period)
        sig = Signal("hold", closes[-1], atr=a[-1])
        if None in (line[-1], line[-2], signal[-1], signal[-2]):
            sig.reason = "недостатньо даних"
            return sig
        bull = line[-2] <= signal[-2] and line[-1] > signal[-1]
        bear = line[-2] >= signal[-2] and line[-1] < signal[-1]
        if bull:
            sig.action, sig.reason = "buy", "MACD перетнув сигнальну вгору"
        elif bear:
            sig.action, sig.reason = "sell", "MACD перетнув сигнальну вниз"
        else:
            sig.reason = "без сигналу"
        return sig


class BollingerStrategy(BaseStrategy):
    """Повернення до середнього: купівля під нижньою смугою, вихід на середній."""
    name = "bollinger"

    def evaluate(self, candles):
        cfg = self.cfg
        closes, highs, lows = self._ohlc(candles)
        mid, upper, lower = ind.bollinger(closes, cfg.bb_period, cfg.bb_std)
        r = ind.rsi(closes, cfg.rsi_period)
        a = ind.atr(highs, lows, closes, cfg.atr_period)
        price = closes[-1]
        sig = Signal("hold", price, atr=a[-1], rsi=r[-1])
        if None in (mid[-1], lower[-1]):
            sig.reason = "недостатньо даних"
            return sig
        if price < lower[-1]:
            sig.action, sig.reason = "buy", "ціна нижче нижньої смуги Боллінджера"
        elif price > mid[-1]:
            sig.action, sig.reason = "sell", "ціна повернулась до середньої"
        else:
            sig.reason = "у межах смуг"
        return sig


class DonchianStrategy(BaseStrategy):
    """Пробій: купівля на пробитті N-періодного максимуму, вихід — пробій мінімуму."""
    name = "donchian"

    def evaluate(self, candles):
        cfg = self.cfg
        closes, highs, lows = self._ohlc(candles)
        up, lo = ind.donchian(highs, lows, cfg.donchian_period)
        a = ind.atr(highs, lows, closes, cfg.atr_period)
        price = closes[-1]
        sig = Signal("hold", price, atr=a[-1])
        if None in (up[-1], lo[-1]):
            sig.reason = "недостатньо даних"
            return sig
        if price > up[-1]:
            sig.action, sig.reason = "buy", f"пробій максимуму {cfg.donchian_period}-періодів"
        elif price < lo[-1]:
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
