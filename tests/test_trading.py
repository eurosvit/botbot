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
from app.trading.risk import position_size, daily_loss_exceeded
from app.trading.strategy import Strategy
from app.trading import backtest

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

    strat = Strategy(cfg)
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
    print(f"    -> угод={res['trades']} дохідність={res['total_return_pct']:+.2f}% "
          f"B&H={res['buy_hold_return_pct']:+.2f}% DD={res['max_drawdown_pct']:.2f}%")


def main():
    print("=" * 50)
    print("ТЕСТИ ТОРГОВОГО МОДУЛЯ (офлайн)")
    print("=" * 50)
    test_indicators()
    test_risk()
    test_strategy_and_backtest()
    print("-" * 50)
    print(f"Результат: {PASS} пройдено, {FAIL} провалено")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
