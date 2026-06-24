"""
Офлайн-демо торгового бота — БЕЗ біржі та БЕЗ бази даних.

Проганяє реальну стратегію (strategy.py) і реальний ризик-менеджмент (risk.py)
на згенерованих свічках та друкує покроковий лог угод і підсумок. Зручно, щоб
«побачити, як воно працює» локально, навіть без доступу до біржі.

Запуск:  python -m app.trading.demo
"""
from __future__ import annotations

import math

from .config import TradingConfig
from .risk import position_size
from .strategy import make_strategy, warmup_bars


def synthetic_candles(n: int = 500) -> list[list[float]]:
    """Висхідний ринок із циклами, щоб EMA перетиналися (реалістичні входи/виходи)."""
    candles = []
    t = 1_700_000_000_000
    for i in range(n):
        base = 100.0 + i * 0.12
        cycle = 9.0 * math.sin(i / 22.0) + 3.5 * math.sin(i / 6.0)
        cl = base + cycle
        o = base + 9.0 * math.sin((i - 1) / 22.0) + 3.5 * math.sin((i - 1) / 6.0)
        h = max(o, cl) + 1.5
        low = min(o, cl) - 1.5
        candles.append([t + i * 3600_000, o, h, low, cl, 1000.0])
    return candles


def run_demo(cfg: TradingConfig, candles: list[list[float]]) -> None:
    strat = make_strategy(cfg)
    cash = cfg.paper_balance
    position = None
    trades = []
    warmup = warmup_bars(cfg)

    print("=" * 64)
    print(f"ДЕМО (офлайн) | стратегія {cfg.strategy} | старт {cfg.paper_balance:.2f} | ризик/угоду {cfg.risk_per_trade*100:.0f}%")
    print(f"ATR SL×{cfg.atr_sl_mult} TP×{cfg.atr_tp_mult}")
    print("=" * 64)

    for i in range(warmup, len(candles)):
        high, low, close = candles[i][2], candles[i][3], candles[i][4]

        if position:
            exit_price = reason = None
            if low <= position["sl"]:
                exit_price, reason = position["sl"], "SL"
            elif high >= position["tp"]:
                exit_price, reason = position["tp"], "TP"
            if exit_price:
                pnl = (exit_price - position["entry"]) * position["qty"]
                cash += position["qty"] * exit_price
                trades.append(pnl)
                tag = "✅" if pnl >= 0 else "🔻"
                print(f"  bar {i:>4} {tag} SELL @ {exit_price:8.2f}  ({reason})  PnL {pnl:+8.2f}  cash {cash:9.2f}")
                position = None

        sig = strat.evaluate(candles[: i + 1])

        if position and sig.action == "sell":
            pnl = (close - position["entry"]) * position["qty"]
            cash += position["qty"] * close
            trades.append(pnl)
            tag = "✅" if pnl >= 0 else "🔻"
            print(f"  bar {i:>4} {tag} SELL @ {close:8.2f}  (сигнал)  PnL {pnl:+8.2f}  cash {cash:9.2f}")
            position = None

        if position is None and sig.action == "buy":
            sl, tp = sig.sl_tp(cfg)
            if sl:
                qty = position_size(cash, cash, close, sl, cfg.risk_per_trade)
                if qty > 0:
                    cash -= qty * close
                    position = {"entry": close, "qty": qty, "sl": sl, "tp": tp}
                    print(f"  bar {i:>4} 🟢 BUY  @ {close:8.2f}  qty {qty:7.4f}  SL {sl:7.2f}  TP {tp:7.2f}")

    if position:
        close = candles[-1][4]
        pnl = (close - position["entry"]) * position["qty"]
        cash += position["qty"] * close
        trades.append(pnl)
        print(f"  кінець     ⏹  SELL @ {close:8.2f}  (закриття)  PnL {pnl:+8.2f}")

    wins = [t for t in trades if t > 0]
    print("-" * 64)
    print(f"Угод: {len(trades)} | прибуткових: {len(wins)} "
          f"({(len(wins)/len(trades)*100) if trades else 0:.0f}%)")
    print(f"Старт: {cfg.paper_balance:.2f}  →  Фінал: {cash:.2f}  "
          f"({(cash/cfg.paper_balance-1)*100:+.2f}%)")
    print(f"Buy & Hold за період: {(candles[-1][4]/candles[warmup][4]-1)*100:+.2f}%")
    print("=" * 64)
    print("⚠️  Це синтетичні дані для демонстрації логіки, НЕ прогноз прибутку.")


def main():
    cfg = TradingConfig.from_env()
    cfg.mode = "backtest"
    cfg.rsi_overbought = 95  # на синтетиці RSI на кросоверах високий — даємо угодам відбутися
    run_demo(cfg, synthetic_candles(500))


if __name__ == "__main__":
    main()
