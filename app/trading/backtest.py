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
from .risk import position_size, pnl
from .strategy import make_strategy, warmup_bars

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
    strat = make_strategy(cfg)
    cash = cfg.paper_balance          # реалізований баланс
    position = None  # {"side", "entry", "qty", "sl", "tp"}
    trades: list[dict] = []
    peak = cash
    max_dd = 0.0
    warmup = warmup_bars(cfg)

    # Індикатори рахуємо ОДИН раз на всю серію (O(N) замість O(N²)).
    closes = [c[4] for c in candles]
    highs = [c[2] for c in candles]
    lows = [c[3] for c in candles]
    inddata = strat.indicators(closes, highs, lows)

    def close_pos(exit_price: float, reason: str) -> None:
        nonlocal cash, position
        p = pnl(position["side"], position["entry"], exit_price, position["qty"])
        cash += p
        notional = position["qty"] * position["entry"]
        trades.append({"pnl": p, "pnl_pct": (p / notional * 100) if notional else 0.0,
                       "reason": reason, "side": position["side"]})
        position = None

    for i in range(warmup, len(candles)):
        high, low, close = candles[i][2], candles[i][3], candles[i][4]

        # 1) Спершу керуємо відкритою позицією (intrabar SL/TP, з урахуванням боку).
        if position:
            if position["side"] == "long":
                if low <= position["sl"]:
                    close_pos(position["sl"], "SL")
                elif high >= position["tp"]:
                    close_pos(position["tp"], "TP")
            else:  # short
                if high >= position["sl"]:
                    close_pos(position["sl"], "SL")
                elif low <= position["tp"]:
                    close_pos(position["tp"], "TP")

        # 2) Сигнал на барі i (за попередньо порахованими індикаторами).
        signal = strat.signal_at(i, closes, inddata)

        # Вихід за протилежним сигналом.
        if position:
            if position["side"] == "long" and signal.action == "sell":
                close_pos(close, "exit-signal")
            elif position["side"] == "short" and signal.action == "buy":
                close_pos(close, "exit-signal")

        # 3) Входи: buy → long; sell → short (якщо дозволено).
        if position is None:
            side = "long" if signal.action == "buy" else ("short" if signal.action == "sell" and cfg.allow_shorts else None)
            if side:
                sl, tp = signal.levels(cfg, side)
                if sl:
                    qty = position_size(cash, cash, close, sl, cfg.risk_per_trade,
                                        side=side, leverage=cfg.leverage)
                    if qty > 0:
                        position = {"side": side, "entry": close, "qty": qty, "sl": sl, "tp": tp}

        # 4) Облік капіталу та просадки (нереалізований PnL).
        unreal = pnl(position["side"], position["entry"], close, position["qty"]) if position else 0.0
        equity = cash + unreal
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak)

    # Закрити позицію по останній ціні.
    if position:
        close_pos(candles[-1][4], "end")

    final = cash
    wins = [t for t in trades if t["pnl"] > 0]
    total_ret = (final / cfg.paper_balance - 1) * 100
    bh_ret = (candles[-1][4] / candles[warmup][4] - 1) * 100  # buy & hold для порівняння

    return {
        "symbol": symbol,
        "strategy": cfg.strategy,
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
    print(f"Бектест {r['symbol']} | стратегія: {r.get('strategy','?')} | свічок: {r['candles']}")
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
