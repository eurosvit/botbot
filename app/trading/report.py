"""
Швидкий порівняльний звіт стратегій на історії — одна команда, готовий результат.

Для кожної пари проганяє бектест усіма стратегіями і друкує таблицю
(дохідність / buy&hold / просадка / win-rate / угоди), а також зберігає звіт
у файл trade_report.txt — його зручно надіслати/вставити для аналізу.

Запуск:
  python -m app.trading.report                 # пари з TRADE_SYMBOLS
  python -m app.trading.report BTC/USDT ETH/USDT SOL/USDT 1500
"""
from __future__ import annotations

import logging
import sys
from dataclasses import replace

from .backtest import fetch_history, run
from .config import TradingConfig
from .market import Market
from .strategy import STRATEGIES

log = logging.getLogger(__name__)


def run_for_symbol(cfg: TradingConfig, symbol: str, candles: list[list[float]]) -> list[dict]:
    """Бектест усіма стратегіями для однієї пари."""
    out = []
    for name in STRATEGIES:
        c = replace(cfg, strategy=name, mode="backtest")
        try:
            out.append(run(c, symbol, candles))
        except Exception as e:
            log.warning("%s/%s: %s", symbol, name, e)
    out.sort(key=lambda r: r["total_return_pct"], reverse=True)
    return out


def _format_symbol(symbol: str, results: list[dict]) -> str:
    lines = [f"\n### {symbol}  (свічок: {results[0]['candles'] if results else 0})",
             f"{'стратегія':<11} {'дохід%':>8} {'B&H%':>8} {'просадка%':>10} {'win%':>6} {'угод':>5}"]
    for r in results:
        lines.append(f"{r['strategy']:<11} {r['total_return_pct']:>8.2f} {r['buy_hold_return_pct']:>8.2f} "
                     f"{r['max_drawdown_pct']:>10.2f} {r['win_rate']:>6.1f} {r['trades']:>5d}")
    if results:
        best = results[0]
        lines.append(f"→ краща за дохідністю: {best['strategy']} ({best['total_return_pct']:+.2f}%)")
    return "\n".join(lines)


def scan(cfg: TradingConfig, symbols: list[str], total: int) -> str:
    market = Market(cfg)
    header = (f"ЗВІТ ПО СТРАТЕГІЯХ | біржа: {cfg.exchange} | ринок: {cfg.market_type} | "
              f"тф: {cfg.timeframe} | старт-баланс: {cfg.paper_balance:.0f} | ризик/угоду: {cfg.risk_per_trade*100:.0f}%")
    blocks = [header, "=" * len(header)]
    for symbol in symbols:
        candles = fetch_history(market, symbol, total)
        if len(candles) < 100:
            blocks.append(f"\n### {symbol}: недостатньо історії ({len(candles)})")
            continue
        blocks.append(_format_symbol(symbol, run_for_symbol(cfg, symbol, candles)))
    blocks.append("\n" + "-" * 60)
    blocks.append("Як читати: 'дохід%' — підсумок стратегії; 'B&H%' — якщо просто тримати; "
                  "'просадка%' — найбільше падіння капіталу (менше = спокійніше); "
                  "'win%' — частка прибуткових угод. ⚠️ Минула дохідність не гарантує майбутню.")
    return "\n".join(blocks)


def main():
    logging.basicConfig(level=logging.WARNING)
    cfg = TradingConfig.from_env()
    args = sys.argv[1:]
    total = 1500
    if args and args[-1].isdigit():
        total = int(args[-1])
        args = args[:-1]
    symbols = [a.upper() for a in args] if args else cfg.symbols

    text = scan(cfg, symbols, total)
    print(text)
    with open("trade_report.txt", "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print("\n📄 Збережено у trade_report.txt — можеш надіслати цей файл для аналізу.")


if __name__ == "__main__":
    main()
