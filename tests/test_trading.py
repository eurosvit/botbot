"""
Офлайн-тести торгового модуля: перевіряють чисту логіку (індикатори, стратегію,
ризик, бектест) без мережі та без БД. Запуск:  python tests/test_trading.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.trading import indicators as ind
from app.trading.config import TradingConfig
from app.trading.risk import position_size, daily_loss_exceeded, pnl
from app.trading.strategy import make_strategy, warmup_bars, STRATEGIES
from app.trading import backtest, optimize, report

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}")


def test_indicators():
    print("indicators:")
    data = [float(i) for i in range(1, 21)]  # 1..20, монотонний ріст
    s = ind.sma(data, 5)
    check("sma None до періоду", s[3] is None and s[4] is not None)
    check("sma(1..5)=3", abs(s[4] - 3.0) < 1e-9)

    e = ind.ema(data, 5)
    check("ema визначено з періоду", e[4] is not None and e[-1] is not None)
    check("ema зростає на висхідному ряді", e[-1] > e[5])

    closes = [10, 11, 10.5, 11.5, 12, 11, 13, 12.5, 14, 15, 14.5, 16, 17, 16.5, 18, 19]
    r = ind.rsi(closes, 14)
    check("rsi у [0,100]", all(0 <= x <= 100 for x in r if x is not None))

    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    a = ind.atr(highs, lows, closes, 14)
    check("atr додатній", a[-1] is not None and a[-1] > 0)

    mid, up, lo = ind.bollinger(closes, 5, 2.0)
    check("bollinger: верхня > середня > нижня",
          up[-1] is not None and up[-1] > mid[-1] > lo[-1])

    dup, dlo = ind.donchian(highs, lows, 5)
    check("donchian: верхня >= нижня", dup[-1] is not None and dup[-1] >= dlo[-1])

    line, sigl, hist = ind.macd(closes, 3, 6, 3)
    check("macd: усі лінії визначені в кінці",
          line[-1] is not None and sigl[-1] is not None and hist[-1] is not None)


def test_risk():
    print("risk:")
    # equity=1000, ризик 1% => 10$. SL на 5% нижче входу (100 -> 95), ризик/од=5 => qty=2
    qty = position_size(1000, 1000, 100, 95, 0.01)
    check("розмір за ризиком = 2", abs(qty - 2.0) < 1e-9)

    # обмеження кешем: кешу лише 50$ при ціні 100 => максимум 0.5
    qty2 = position_size(1000, 50, 100, 95, 0.01)
    check("обмеження готівкою", abs(qty2 - 0.5) < 1e-9)

    check("некоректний SL => 0", position_size(1000, 1000, 100, 100, 0.01) == 0)
    check("денний стоп спрацьовує", daily_loss_exceeded(-60, 1000, 0.05) is True)
    check("денний стоп не спрацьовує", daily_loss_exceeded(-10, 1000, 0.05) is False)

    # short: стоп вище входу (100 -> 105), ризик/од=5 => qty=2
    check("short розмір за ризиком = 2",
          abs(position_size(1000, 1000, 100, 105, 0.01, side="short") - 2.0) < 1e-9)
    check("short некоректний SL (нижче входу) => 0",
          position_size(1000, 1000, 100, 95, 0.01, side="short") == 0)
    # плече збільшує купівельну спроможність: cash=100 => без плеча cap=1, з x5 cap=5
    check("без плеча обмеження кешем = 1", abs(position_size(1000, 100, 100, 95, 0.01) - 1.0) < 1e-9)
    check("плече x5 знімає обмеження до ризику = 2",
          abs(position_size(1000, 100, 100, 95, 0.01, leverage=5) - 2.0) < 1e-9)
    check("pnl long", abs(pnl("long", 100, 110, 2) - 20.0) < 1e-9)
    check("pnl short", abs(pnl("short", 100, 90, 2) - 20.0) < 1e-9)


def _synthetic_trend(n=400):
    """Свічки з висхідним трендом + цикли, щоб EMA перетиналися (входи/виходи)."""
    candles = []
    t = 1_700_000_000_000
    for i in range(n):
        # загальний підйом + два цикли різного періоду => регулярні кросовери
        base = 100.0 + i * 0.15
        cycle = 8.0 * math.sin(i / 20.0) + 3.0 * math.sin(i / 6.0)
        cl = base + cycle
        o = base + 8.0 * math.sin((i - 1) / 20.0) + 3.0 * math.sin((i - 1) / 6.0)
        h = max(o, cl) + 1.5
        low = min(o, cl) - 1.5
        candles.append([t + i * 3600_000, o, h, low, cl, 1000])
    return candles


def test_strategy_and_backtest():
    print("strategy + backtest:")
    cfg = TradingConfig.from_env()
    cfg.mode = "backtest"
    # На синтетичному висхідному ряді RSI на кросоверах високий; послаблюємо
    # поріг, щоб тест реально прогнав шлях входу/виходу/SL/TP.
    cfg.rsi_overbought = 95
    candles = _synthetic_trend(400)

    strat = make_strategy(cfg)
    sig = strat.evaluate(candles)
    check("сигнал має валідний action", sig.action in ("buy", "sell", "hold"))
    check("ATR порахований у сигналі", sig.atr is not None)
    sl, tp = sig.sl_tp(cfg)
    if sl is not None:
        check("SL нижче TP", sl < tp)

    res = backtest.run(cfg, "TEST/USDT", candles)
    check("бектест повертає число угод", isinstance(res["trades"], int))
    check("фінальний баланс додатній", res["final_balance"] > 0)
    check("просадка в [0,100]", 0 <= res["max_drawdown_pct"] <= 100)
    print(f"    -> [{cfg.strategy}] угод={res['trades']} дохідність={res['total_return_pct']:+.2f}% "
          f"B&H={res['buy_hold_return_pct']:+.2f}% DD={res['max_drawdown_pct']:.2f}%")


def test_all_strategies():
    print("усі стратегії:")
    candles = _synthetic_trend(400)
    for name in STRATEGIES:
        cfg = TradingConfig.from_env()
        cfg.mode = "backtest"
        cfg.strategy = name
        cfg.rsi_overbought = 95
        strat = make_strategy(cfg)
        sig = strat.evaluate(candles)
        ok = sig.action in ("buy", "sell", "hold")
        res = backtest.run(cfg, "TEST/USDT", candles)
        ok = ok and res["final_balance"] > 0 and isinstance(res["trades"], int)
        check(f"{name}: оцінка + бектест ок", ok)
        print(f"    -> [{name}] угод={res['trades']} дохідність={res['total_return_pct']:+.2f}% "
              f"DD={res['max_drawdown_pct']:.2f}%")


def test_futures_shorts():
    print("ф'ючерси + шорти:")
    # валідація конфігу
    cfg = TradingConfig.from_env()
    cfg.market_type = "swap"; cfg.leverage = 3; cfg.allow_shorts = True; cfg.strategy = "macd"
    try:
        cfg.validate(); ok = True
    except Exception:
        ok = False
    check("swap+плече+шорти валідуються", ok)

    bad = TradingConfig.from_env()
    bad.allow_shorts = True  # spot + shorts -> помилка
    try:
        bad.validate(); rejected = False
    except Exception:
        rejected = True
    check("шорти на споті відхиляються", rejected)

    # ф'ючерсний бектест із шортами проганяється коректно
    cfg.mode = "backtest"
    candles = _synthetic_trend(400)
    res = backtest.run(cfg, "TEST/USDT", candles)
    check("ф'ючерсний бектест працює", isinstance(res["trades"], int) and res["final_balance"] > 0)
    print(f"    -> [swap x3, shorts] угод={res['trades']} дохідність={res['total_return_pct']:+.2f}% "
          f"DD={res['max_drawdown_pct']:.2f}%")


def test_report():
    print("звіт:")
    cfg = TradingConfig.from_env()
    cfg.mode = "backtest"
    candles = _synthetic_trend(450)
    results = report.run_for_symbol(cfg, "TEST/USDT", candles)
    check("звіт покриває всі стратегії", len(results) == len(STRATEGIES))
    check("звіт відсортований за дохідністю (спадання)",
          all(results[i]["total_return_pct"] >= results[i + 1]["total_return_pct"]
              for i in range(len(results) - 1)))


def test_optimizer():
    print("оптимізатор:")
    cfg = TradingConfig.from_env()
    cfg.mode = "backtest"
    cfg.strategy = "macd"   # на синтетиці дає достатньо угод для оцінки
    candles = _synthetic_trend(500)
    results = optimize.optimize(cfg, "TEST/USDT", candles, top=5)
    check("оптимізатор повертає результати", len(results) > 0)
    check("результати відсортовані за score (спадання)",
          all(results[i]["score"] >= results[i + 1]["score"] for i in range(len(results) - 1)))
    check("кожен результат має параметри", all("params" in r for r in results))
    check("знайдено хоча б одну надійну комбінацію (score скінченний)",
          results[0]["score"] != float("-inf"))
    best = results[0]
    print(f"    -> найкраще: score={best['score']:.2f} ret={best['total_return_pct']:+.2f}% "
          f"угод={best['trades']} params={best['params']}")


def main():
    print("=" * 50)
    print("ТЕСТИ ТОРГОВОГО МОДУЛЯ (офлайн)")
    print("=" * 50)
    test_indicators()
    test_risk()
    test_strategy_and_backtest()
    test_all_strategies()
    test_futures_shorts()
    test_report()
    test_optimizer()
    print("-" * 50)
    print(f"Результат: {PASS} пройдено, {FAIL} провалено")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
