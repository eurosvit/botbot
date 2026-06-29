"""
Самовдосконалення бота:

1. apply_overrides — накладає авто-підібрані параметри (з БД) поверх env,
   тож «навчені» налаштування підхоплюються живим ботом.
2. autotune — walk-forward-подібний перебір: на свіжих реальних даних шукає
   найкращу стратегію+параметри й застосовує їх (із запобіжниками).
3. performance_review — текстовий само-аналіз результатів для Telegram.

⚠️ Чесно: підбір на минулому ≠ гарантія майбутнього (ризик перенавчання).
Тому застосовуємо лише прибуткові на історії варіанти й логуємо кожну зміну.
"""
from __future__ import annotations

import logging
from dataclasses import replace

from .config import TradingConfig
from . import store

log = logging.getLogger(__name__)

_INT = {"ema_fast", "ema_slow", "rsi_period", "atr_period", "bb_period",
        "donchian_period", "macd_fast", "macd_slow", "macd_signal", "trend_ema"}
_FLOAT = {"atr_sl_mult", "atr_tp_mult", "rsi_overbought", "rsi_oversold", "bb_std"}
_STR = {"strategy"}


def apply_overrides(cfg: TradingConfig) -> TradingConfig:
    """Накладає збережені авто-параметри поверх конфігу."""
    try:
        ov = store.get_overrides()
    except Exception:
        return cfg
    changes = {}
    for k, v in ov.items():
        try:
            if k in _INT:
                changes[k] = int(float(v))
            elif k in _FLOAT:
                changes[k] = float(v)
            elif k in _STR:
                changes[k] = str(v)
        except (TypeError, ValueError):
            continue
    return replace(cfg, **changes) if changes else cfg


def autotune(cfg: TradingConfig, candles_n: int = 1000) -> dict:
    """Підбирає найкращу стратегію+параметри на свіжих даних і застосовує (якщо вони в плюсі)."""
    from .market import Market
    from .backtest import fetch_history
    from .optimize import optimize, GRIDS
    from .strategy import STRATEGIES

    base = replace(cfg, mode="backtest")
    symbol = cfg.symbols[0]
    market = Market(base)
    candles = fetch_history(market, symbol, candles_n)
    if len(candles) < 200:
        return {"applied": False, "reason": f"мало історії ({len(candles)})"}

    best = None
    for name in STRATEGIES:
        if name not in GRIDS:
            continue
        res = optimize(replace(base, strategy=name), symbol, candles, top=1)
        if res and res[0]["score"] not in (float("inf"), float("-inf")):
            cand = {"strategy": name, **res[0]}
            if best is None or cand["score"] > best["score"]:
                best = cand

    if not best:
        return {"applied": False, "reason": "немає надійних комбінацій (замало угод)"}
    if best["total_return_pct"] <= 0:
        return {"applied": False, "reason": "усі варіанти в мінусі — лишаємо поточні налаштування",
                "best_strategy": best["strategy"], "best_return_pct": best["total_return_pct"]}

    overrides = {"strategy": best["strategy"]}
    overrides.update({k: str(v) for k, v in best["params"].items()})
    store.save_overrides(overrides)
    log.info("autotune застосував %s %s (ret=%.2f%%)", best["strategy"], best["params"],
             best["total_return_pct"])
    return {
        "applied": True, "symbol": symbol, "strategy": best["strategy"],
        "params": best["params"], "return_pct": round(best["total_return_pct"], 2),
        "max_drawdown_pct": round(best["max_drawdown_pct"], 2),
        "trades": best["trades"], "score": round(best["score"], 2),
    }


def format_autotune(result: dict) -> str:
    if result.get("applied"):
        p = " ".join(f"{k}={v}" for k, v in result["params"].items())
        return (f"🧠 <b>Авто-тюнінг</b>\n"
                f"Нова конфігурація на основі {result['symbol']}:\n"
                f"Стратегія: <b>{result['strategy']}</b>\n{p}\n"
                f"На історії: дохід {result['return_pct']:+.2f}%, "
                f"просадка {result['max_drawdown_pct']:.2f}%, угод {result['trades']}")
    return f"🧠 <b>Авто-тюнінг</b>: без змін — {result.get('reason', '')}"


def performance_review(mode: str) -> str:
    """Текстовий само-аналіз результатів за стратегіями та парами."""
    rows = store.performance_breakdown(mode)
    stats = store.daily_stats(mode)
    if not rows:
        return "📈 <b>Тижневий розбір</b>: ще немає закритих угод для аналізу."
    lines = ["📈 <b>Тижневий розбір</b>",
             f"Капітал: {stats['equity']:.2f} {''}  |  усього угод: {stats['trades_total']}",
             "——————————————", "Розбивка (стратегія · пара):"]
    for r in rows:
        n = int(r["n"]); wins = int(r["wins"]); pnl = float(r["pnl"])
        wr = (wins / n * 100) if n else 0
        emoji = "✅" if pnl >= 0 else "🔻"
        lines.append(f"{emoji} {r['strategy']} · {r['symbol']}: {n} угод, "
                     f"win {wr:.0f}%, PnL {pnl:+.2f}")
    best = rows[0]; worst = rows[-1]
    lines.append("——————————————")
    lines.append(f"Найкраще: {best['strategy']}·{best['symbol']} ({float(best['pnl']):+.2f})")
    if worst is not best:
        lines.append(f"Найгірше: {worst['strategy']}·{worst['symbol']} ({float(worst['pnl']):+.2f})")
    return "\n".join(lines)
