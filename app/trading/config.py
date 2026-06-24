"""
Конфігурація торгового модуля. Усі параметри читаються з env-змінних,
у тому ж стилі, що й решта проєкту (os.getenv).
"""
import os
from dataclasses import dataclass, field


def _f(name: str, default: str) -> float:
    return float(os.getenv(name, default))


def _i(name: str, default: str) -> int:
    return int(os.getenv(name, default))


def _b(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


def _list(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [x.strip().upper() for x in raw.split(",") if x.strip()]


@dataclass
class TradingConfig:
    # --- Біржа / ринок ---
    exchange: str                 # будь-яка біржа, що підтримується ccxt (binance, bybit, ...)
    symbols: list[str]            # перелік торгових пар, напр. ["BTC/USDT", "ETH/USDT"]
    timeframe: str                # таймфрейм свічок: 1m, 5m, 15m, 1h, 4h, 1d
    quote_currency: str           # валюта котирування (USDT)

    # --- Режим роботи ---
    mode: str                     # paper | live | backtest
    testnet: bool                 # для live: торгувати на sandbox/testnet біржі

    # --- Капітал ---
    paper_balance: float          # стартовий віртуальний баланс для paper-режиму

    # --- Стратегія ---
    strategy: str                 # ema_rsi | macd | bollinger | donchian
    ema_fast: int
    ema_slow: int
    rsi_period: int
    rsi_overbought: float
    rsi_oversold: float
    atr_period: int
    atr_sl_mult: float            # стоп-лосс = entry - atr_sl_mult * ATR
    atr_tp_mult: float            # тейк-профіт = entry + atr_tp_mult * ATR
    bb_period: int                # смуги Боллінджера: період
    bb_std: float                 # смуги Боллінджера: к-сть стд. відхилень
    donchian_period: int          # канал Дончіана: період пробою
    macd_fast: int
    macd_slow: int
    macd_signal: int

    # --- Ризик-менеджмент ---
    risk_per_trade: float         # частка капіталу під ризиком на угоду (0.01 = 1%)
    max_open_positions: int       # макс. одночасних відкритих позицій
    max_daily_loss_pct: float     # денний стоп: при втраті X% капіталу бот зупиняє нові входи

    # --- Цикл ---
    poll_seconds: int             # пауза між ітераціями торгового циклу
    candle_limit: int             # скільки свічок тягнути для розрахунку індикаторів

    # --- Сповіщення ---
    notify: bool                  # надсилати сповіщення в Telegram

    @classmethod
    def from_env(cls) -> "TradingConfig":
        return cls(
            exchange=os.getenv("TRADE_EXCHANGE", "binance"),
            symbols=_list("TRADE_SYMBOLS", "BTC/USDT,ETH/USDT"),
            timeframe=os.getenv("TRADE_TIMEFRAME", "1h"),
            quote_currency=os.getenv("TRADE_QUOTE", "USDT"),
            mode=os.getenv("TRADE_MODE", "paper").strip().lower(),
            testnet=_b("TRADE_TESTNET", "false"),
            paper_balance=_f("TRADE_PAPER_BALANCE", "1000"),
            strategy=os.getenv("TRADE_STRATEGY", "ema_rsi").strip().lower(),
            ema_fast=_i("TRADE_EMA_FAST", "12"),
            ema_slow=_i("TRADE_EMA_SLOW", "26"),
            rsi_period=_i("TRADE_RSI_PERIOD", "14"),
            rsi_overbought=_f("TRADE_RSI_OVERBOUGHT", "70"),
            rsi_oversold=_f("TRADE_RSI_OVERSOLD", "30"),
            atr_period=_i("TRADE_ATR_PERIOD", "14"),
            atr_sl_mult=_f("TRADE_ATR_SL_MULT", "1.5"),
            atr_tp_mult=_f("TRADE_ATR_TP_MULT", "3.0"),
            bb_period=_i("TRADE_BB_PERIOD", "20"),
            bb_std=_f("TRADE_BB_STD", "2.0"),
            donchian_period=_i("TRADE_DONCHIAN_PERIOD", "20"),
            macd_fast=_i("TRADE_MACD_FAST", "12"),
            macd_slow=_i("TRADE_MACD_SLOW", "26"),
            macd_signal=_i("TRADE_MACD_SIGNAL", "9"),
            risk_per_trade=_f("TRADE_RISK_PER_TRADE", "0.01"),
            max_open_positions=_i("TRADE_MAX_POSITIONS", "3"),
            max_daily_loss_pct=_f("TRADE_MAX_DAILY_LOSS_PCT", "0.05"),
            poll_seconds=_i("TRADE_POLL_SECONDS", "60"),
            candle_limit=_i("TRADE_CANDLE_LIMIT", "200"),
            notify=_b("TRADE_NOTIFY", "true"),
        )

    def validate(self) -> None:
        if self.mode not in ("paper", "live", "backtest"):
            raise ValueError(f"Невідомий TRADE_MODE: {self.mode}")
        if self.strategy not in ("ema_rsi", "macd", "bollinger", "donchian"):
            raise ValueError(f"Невідома TRADE_STRATEGY: {self.strategy}")
        if self.strategy == "ema_rsi" and self.ema_fast >= self.ema_slow:
            raise ValueError("EMA_FAST має бути меншим за EMA_SLOW")
        if self.strategy == "macd" and self.macd_fast >= self.macd_slow:
            raise ValueError("MACD_FAST має бути меншим за MACD_SLOW")
        if not (0 < self.risk_per_trade < 0.5):
            raise ValueError("RISK_PER_TRADE має бути в діапазоні (0, 0.5)")
        if not self.symbols:
            raise ValueError("Не задано жодного символу (TRADE_SYMBOLS)")
