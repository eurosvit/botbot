"""
Підбір параметрів стратегії перебором (grid-search) на історичних даних.

Для обраної стратегії проганяє бектест по сітці параметрів і ранжує комбінації
за ризик-скоригованим показником (дохідність / просадка). Допомагає знайти
кращі налаштування, перш ніж торгувати.

Запуск:
  TRADE_STRATEGY=ema_rsi python -m app.trading.optimize BTC/USDT 1500
  TRADE_STRATEGY=donchian python -m app.trading.optimize ETH/USDT
"""
from __future__ import annotations

import itertools
import logging
import sys
from dataclasses import replace

from .backtest import fetch_history, run
from .config import TradingConfig
from .market import Market

log = logging.getLogger(__name__)

MIN_TRADES = 5  # комбінації з меншою кількістю угод вважаємо ненадійними

# Сітки параметрів для перебору (свідомо компактні, щоб працювало швидко).
GRIDS: dict[str, dict[str, list]] = {
    "ema_rsi": {
        "ema_fast": [9, 12, 20],
        "ema_slow": [26, 50],
        "rsi_overbought": [65, 70, 75],
        "atr_sl_mult": [1.0, 1.5, 2.0],
        "atr_tp_mult": [2.0, 3.0],
    },
    "macd": {
        "macd_fast": [8, 12],
        "macd_slow": [21, 26],
        "atr_sl_mult": [1.0, 1.5, 2.0],
        "atr_tp_mult": [2.0, 3.0, 4.0],
    },
    "bollinger": {
        "bb_period": [14, 20],
        "bb_std": [2.0, 2.5],
        "atr_sl_mult": [1.0, 1.5, 2.0],
        "atr_tp_mult": [2.0, 3.0, 4.0],
    },
    "donchian": {
        "donchian_period": [10, 20, 30, 55],
        "atr_sl_mult": [1.0, 1.5, 2.0],
        "atr_tp_mult": [2.0, 3.0, 4.0],
    },
}


def _score(r: dict) -> float:
    """Ризик-скоригований показник: дохідність на одиницю просадки (Calmar-подібний).
    Комбінації з малою к-стю угод відсікаємо, щоб не ловити випадковість."""
    if r["trades"] < MIN_TRADES:
        return float("-inf")
    return r["total_return_pct"] / max(r["max_drawdown_pct"], 1.0)


def optimize(cfg: TradingConfig, symbol: str, candles: list[list[float]], top: int = 10) -> list[dict]:
    grid = GRIDS.get(cfg.strategy)
    if not grid:
        raise ValueError(f"Немає сітки параметрів для стратегії '{cfg.strategy}'")
    keys = list(grid)
    results: list[dict] = []
    for combo in itertools.product(*[grid[k] for k in keys]):
        ov = dict(zip(keys, combo))
        if ov.get("ema_fast", 0) >= ov.get("ema_slow", 10 ** 9):
            continue
        if ov.get("macd_fast", 0) >= ov.get("macd_slow", 10 ** 9):
            continue
        c = replace(cfg, **ov)
        try:
            r = run(c, symbol, candles)
        except Exception:
            continue
        r["params"] = ov
        r["score"] = _score(r)
        results.append(r)
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top]


def _fmt_params(p: dict) -> str:
    return " ".join(f"{k}={v}" for k, v in p.items())


def _print(symbol: str, strategy: str, results: list[dict]) -> None:
    print("=" * 84)
    print(f"Оптимізація {symbol} | стратегія: {strategy} | комбінацій у ТОП: {len(results)}")
    print("-" * 84)
    print(f"{'score':>7} {'ret%':>8} {'B&H%':>8} {'DD%':>7} {'win%':>6} {'угод':>5}  параметри")
    for r in results:
        sc = r["score"]
        sc_s = f"{sc:7.2f}" if sc != float("-inf") else "   —  "
        print(f"{sc_s} {r['total_return_pct']:8.2f} {r['buy_hold_return_pct']:8.2f} "
              f"{r['max_drawdown_pct']:7.2f} {r['win_rate']:6.1f} {r['trades']:5d}  {_fmt_params(r['params'])}")
    print("=" * 84)
    if results and results[0]["score"] != float("-inf"):
        best = results[0]["params"]
        print("Найкраща комбінація як env-змінні:")
        env = {"ema_fast": "TRADE_EMA_FAST", "ema_slow": "TRADE_EMA_SLOW",
               "rsi_overbought": "TRADE_RSI_OVERBOUGHT", "atr_sl_mult": "TRADE_ATR_SL_MULT",
               "atr_tp_mult": "TRADE_ATR_TP_MULT", "bb_period": "TRADE_BB_PERIOD",
               "bb_std": "TRADE_BB_STD", "donchian_period": "TRADE_DONCHIAN_PERIOD",
               "macd_fast": "TRADE_MACD_FAST", "macd_slow": "TRADE_MACD_SLOW"}
        for k, v in best.items():
            print(f"  {env.get(k, k.upper())}={v}")
    print("⚠️  Підбір на історії ≠ гарантія в майбутньому (ризик перенавчання). "
          "Перевіряй кращі параметри ще й у paper-режимі.")


def main():
    logging.basicConfig(level=logging.WARNING)
    cfg = TradingConfig.from_env()
    cfg.mode = "backtest"
    symbol = sys.argv[1] if len(sys.argv) > 1 else cfg.symbols[0]
    total = int(sys.argv[2]) if len(sys.argv) > 2 else 1500
    market = Market(cfg)
    candles = fetch_history(market, symbol, total)
    if len(candles) < 100:
        print(f"{symbol}: недостатньо історії ({len(candles)})")
        return
    results = optimize(cfg, symbol, candles)
    _print(symbol, cfg.strategy, results)


if __name__ == "__main__":
    main()
