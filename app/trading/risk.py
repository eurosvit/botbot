"""
Ризик-менеджмент. Найважливіший модуль для виживання депозиту:
розмір позиції визначається ризиком на угоду, а не «на скільки вистачить грошей».
Підтримує і long, і short (для ф'ючерсів) та плече.
"""
from __future__ import annotations


def position_size(equity: float, cash: float, entry: float, stop_loss: float,
                  risk_per_trade: float, side: str = "long", leverage: int = 1) -> float:
    """
    Скільки одиниць активу взяти, щоб при спрацюванні стоп-лоссу
    втратити не більше risk_per_trade від капіталу.

        ризик_на_одиницю = |entry - stop_loss|
        qty = (equity * risk_per_trade) / ризик_на_одиницю

    Додатково обмежуємо доступною купівельною спроможністю (cash * leverage).
    Для long стоп має бути нижче входу, для short — вище. Інакше 0.
    """
    if entry <= 0 or stop_loss <= 0:
        return 0.0
    if side == "long" and stop_loss >= entry:
        return 0.0
    if side == "short" and stop_loss <= entry:
        return 0.0
    risk_per_unit = abs(entry - stop_loss)
    if risk_per_unit <= 0:
        return 0.0
    qty = (equity * risk_per_trade) / risk_per_unit
    max_qty_by_buying_power = (cash * max(leverage, 1)) / entry
    return max(0.0, min(qty, max_qty_by_buying_power))


def pnl(side: str, entry: float, exit_price: float, qty: float) -> float:
    """Реалізований PnL для long або short."""
    if side == "short":
        return (entry - exit_price) * qty
    return (exit_price - entry) * qty


def daily_loss_exceeded(realized_pnl_today: float, equity: float, max_daily_loss_pct: float) -> bool:
    """True, якщо сьогоднішній збиток перевищив денний ліміт — нові входи блокуються."""
    if equity <= 0:
        return True
    return realized_pnl_today <= -abs(max_daily_loss_pct) * equity
