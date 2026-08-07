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


def _walk_forward_one(base: TradingConfig, name: str, symbol: str, candles: list) -> dict | None:
    """Walk-forward для однієї стратегії: підбір на «старій» частині,
    перевірка на «свіжій» (out-of-sample). Повертає найкращий конфіг, що
    ПІДТВЕРДИВСЯ поза вибіркою, або None."""
    from .backtest import run
    from .optimize import optimize, GRIDS
    from .strategy import warmup_bars
    if name not in GRIDS:
        return None
    n = len(candles)
    wu = warmup_bars(base)
    split = int(n * 0.7)
    in_sample = candles[:split]
    oos = candles[max(0, split - wu):]          # хвіст in-sample як розігрів для індикаторів
    if len(in_sample) < wu + 30 or len(oos) < wu + 10:
        return None

    best = None
    for c in optimize(replace(base, strategy=name), symbol, in_sample, top=15):
        # має бути ХОРОШИМ на in-sample…
        if c["trades"] < 5 or c["total_return_pct"] <= 0:
            continue
        cfg2 = replace(base, strategy=name, **c["params"])
        oos_r = run(cfg2, symbol, oos)
        # …І ПІДТВЕРДИТИСЬ на out-of-sample (пріоритет стабільності: DD ≤ 10%, win ≥ 55%):
        if (oos_r["trades"] < 3 or oos_r["total_return_pct"] <= 0
                or oos_r["max_drawdown_pct"] > 10 or oos_r["win_rate"] < 55):
            continue
        cand = {"strategy": name, "params": c["params"],
                "is_win": c["win_rate"], "is_return": c["total_return_pct"],
                "oos_win": oos_r["win_rate"], "oos_return": oos_r["total_return_pct"],
                "oos_dd": oos_r["max_drawdown_pct"], "oos_trades": oos_r["trades"]}
        # обираємо за результатами САМЕ поза вибіркою (win-rate, потім дохід)
        if best is None or (cand["oos_win"], cand["oos_return"]) > (best["oos_win"], best["oos_return"]):
            best = cand
    return best


def walk_forward_select(base: TradingConfig, names: list, symbol: str, candles: list) -> dict | None:
    """Найкращий підтверджений поза вибіркою конфіг серед стратегій `names`."""
    best = None
    for name in names:
        cand = _walk_forward_one(base, name, symbol, candles)
        if cand and (best is None or (cand["oos_win"], cand["oos_return"]) >
                     (best["oos_win"], best["oos_return"])):
            best = cand
    return best


def autotune(cfg: TradingConfig, candles_n: int = 1200, lock_strategy: str | None = None) -> dict:
    """Walk-forward автотюнінг: застосовує лише конфіг, який підтвердився на
    свіжій (невидимій під час підбору) частині даних — це зменшує перенавчання.

    lock_strategy — якщо задано, тюнимо ЛИШЕ цю стратегію, не перемикаючи.
    """
    from .market import Market
    from .backtest import fetch_history
    from .strategy import STRATEGIES

    base = replace(cfg, mode="backtest")
    symbol = cfg.symbols[0]
    candles = fetch_history(Market(base), symbol, candles_n)
    if len(candles) < 300:
        return {"applied": False, "reason": f"мало історії ({len(candles)})"}

    names = [lock_strategy] if lock_strategy else list(STRATEGIES)
    best = walk_forward_select(base, names, symbol, candles)
    if not best:
        return {"applied": False,
                "reason": "жодна конфігурація не підтвердилась поза вибіркою (walk-forward)"}

    overrides = {"strategy": best["strategy"]}
    overrides.update({k: str(v) for k, v in best["params"].items()})
    store.save_overrides(overrides)
    log.info("autotune застосував %s %s (oos win=%.0f%%, oos ret=%.2f%%)",
             best["strategy"], best["params"], best["oos_win"], best["oos_return"])
    return {
        "applied": True, "symbol": symbol, "strategy": best["strategy"], "params": best["params"],
        "in_sample_win": round(best["is_win"], 1), "in_sample_return": round(best["is_return"], 2),
        "oos_win": round(best["oos_win"], 1), "oos_return": round(best["oos_return"], 2),
        "oos_trades": best["oos_trades"], "oos_drawdown": round(best["oos_dd"], 2),
    }


def format_autotune(result: dict) -> str:
    if result.get("applied"):
        p = " ".join(f"{k}={v}" for k, v in result["params"].items())
        return (f"🧠 <b>Авто-тюнінг</b> (walk-forward)\n"
                f"Стратегія: <b>{result['strategy']}</b> ({result['symbol']})\n{p}\n"
                f"На підборі: {result['in_sample_win']:.0f}% вдалих, {result['in_sample_return']:+.2f}%\n"
                f"✅ Перевірка поза вибіркою: <b>{result['oos_win']:.0f}% вдалих</b>, "
                f"{result['oos_return']:+.2f}%, просадка {result['oos_drawdown']:.2f}%, "
                f"угод {result['oos_trades']}")
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
