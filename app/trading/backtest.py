"""
Бектест стратегії на історичних даних. Дозволяє оцінити поведінку стратегії
ПЕРШ ніж ризикувати грошима. Не торкається БД — повністю в пам'яті.

Запуск:  python -m app.trading.backtest BTC/USDT
"""
from __future__ import annotations

import logging
import sys

from .config import TradingConfig
from .market import Market
from .risk import position_size
from .strategy import Strategy

log = logging.getLogger(__name__)


def fetch_history(market: Market, symbol: str, total: int) -> list[list[float]]:
    """Тягне історію свічок посторінково (ccxt віддає до ~1000 за раз)."""
    out: list[list[float]] = []
    limit = 1000
    since = None
    tf_ms = market.client.parse_timeframe(market.cfg.timeframe) * 1000
    # Стартуємо з минулого: total свічок назад від «зараз».
    now = market.client.milliseconds()
    since = now - total * tf_ms
    while len(out) < total:
        batch = market.client.fetch_ohlcv(symbol, market.cfg.timeframe, since=since, limit=limit)
        if not batch:
            break
        out += batch
        since = batch[-1][0] + tf_ms
        if len(batch) < limit:
            break
    # прибрати дублікати за timestamp
    seen = {}
    for c in out:
        seen[c[0]] = c
    return [seen[k] for k in sorted(seen)]


def run(cfg: TradingConfig, symbol: str, candles: list[list[float]]) -> dict:
    strat = Strategy(cfg)
    cash = cfg.paper_balance
    position = None  # {"entry", "qty", "sl", "tp"}
    trades: list[dict] = []
    equity_curve: list[float] = []
    peak = cash
    max_dd = 0.0

    warmup = max(cfg.ema_slow, cfg.rsi_period, cfg.atr_period) + 2

    for i in range(warmup, len(candles)):
        high = candles[i][2]
        low = candles[i][3]
        close = candles[i][4]

        # 1) Спершу керуємо відкритою позицією (intrabar SL/TP).
        if position:
            exit_price = None
            reason = None
            if low <= position["sl"]:
                exit_price, reason = position["sl"], "SL"
            elif high >= position["tp"]:
                exit_price, reason = position["tp"], "TP"
            if exit_price is not None:
                pnl = (exit_price - position["entry"]) * position["qty"]
                cash += position["qty"] * exit_price
                trades.append({"pnl": pnl, "pnl_pct": (exit_price / position["entry"] - 1) * 100,
                               "reason": reason})
                position = None

        # 2) Сигнал на закритих свічках [0..i].
        signal = strat.evaluate(candles[: i + 1])

        if position and signal.action == "sell":
            pnl = (close - position["entry"]) * position["qty"]
            cash += position["qty"] * close
            trades.append({"pnl": pnl, "pnl_pct": (close / position["entry"] - 1) * 100,
                           "reason": "exit-signal"})
            position = None

        if position is None and signal.action == "buy":
            sl, tp = signal.sl_tp(cfg)
            if sl:
                equity_now = cash
                qty = position_size(equity_now, cash, close, sl, cfg.risk_per_trade)
                if qty > 0:
                    cash -= qty * close
                    position = {"entry": close, "qty": qty, "sl": sl, "tp": tp}

        # 3) Облік капіталу та просадки.
        equity = cash + (position["qty"] * close if position else 0.0)
        equity_curve.append(equity)
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak)

    # Закрити позицію по останній ціні.
    if position:
        close = candles[-1][4]
        cash += position["qty"] * close
        trades.append({"pnl": (close - position["entry"]) * position["qty"],
                       "pnl_pct": (close / position["entry"] - 1) * 100, "reason": "end"})

    final = cash
    wins = [t for t in trades if t["pnl"] > 0]
    total_ret = (final / cfg.paper_balance - 1) * 100
    bh_ret = (candles[-1][4] / candles[warmup][4] - 1) * 100  # buy & hold для порівняння

    return {
        "symbol": symbol,
        "candles": len(candles),
        "trades": len(trades),
        "win_rate": (len(wins) / len(trades) * 100) if trades else 0.0,
        "start_balance": cfg.paper_balance,
        "final_balance": final,
        "total_return_pct": total_ret,
        "buy_hold_return_pct": bh_ret,
        "max_drawdown_pct": max_dd * 100,
    }


def _print(r: dict) -> None:
    print("=" * 48)
    print(f"Бектест {r['symbol']} | свічок: {r['candles']}")
    print("-" * 48)
    print(f"Угод:                 {r['trades']}")
    print(f"Win rate:             {r['win_rate']:.1f}%")
    print(f"Старт:                {r['start_balance']:.2f}")
    print(f"Фінал:                {r['final_balance']:.2f}")
    print(f"Дохідність стратегії: {r['total_return_pct']:+.2f}%")
    print(f"Buy & Hold:           {r['buy_hold_return_pct']:+.2f}%")
    print(f"Макс. просадка:       {r['max_drawdown_pct']:.2f}%")
    print("=" * 48)


def main():
    logging.basicConfig(level=logging.INFO)
    cfg = TradingConfig.from_env()
    cfg.mode = "backtest"
    symbols = [sys.argv[1]] if len(sys.argv) > 1 else cfg.symbols
    market = Market(cfg)
    total = int(sys.argv[2]) if len(sys.argv) > 2 else 1500
    for sym in symbols:
        candles = fetch_history(market, sym, total)
        if len(candles) < 50:
            print(f"{sym}: недостатньо історії")
            continue
        _print(run(cfg, sym, candles))


if __name__ == "__main__":
    main()
