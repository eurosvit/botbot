"""
Ризик-менеджмент. Найважливіший модуль для виживання депозиту:
розмір позиції визначається ризиком на угоду, а не «на скільки вистачить грошей».
"""
from __future__ import annotations


def position_size(equity: float, cash: float, entry: float, stop_loss: float,
                  risk_per_trade: float) -> float:
    """
    Скільки одиниць активу купити, щоб при спрацюванні стоп-лоссу
    втратити не більше risk_per_trade від капіталу.

        ризик_на_одиницю = entry - stop_loss
        qty = (equity * risk_per_trade) / ризик_на_одиницю

    Додатково обмежуємо доступним кешем (не використовуємо плече).
    Повертає 0, якщо вхід некоректний.
    """
    if entry <= 0 or stop_loss <= 0 or stop_loss >= entry:
        return 0.0
    risk_per_unit = entry - stop_loss
    risk_budget = equity * risk_per_trade
    qty = risk_budget / risk_per_unit
    # Не виходимо за межі готівки (спот, без плеча).
    max_qty_by_cash = cash / entry
    return max(0.0, min(qty, max_qty_by_cash))


def daily_loss_exceeded(realized_pnl_today: float, equity: float, max_daily_loss_pct: float) -> bool:
    """True, якщо сьогоднішній збиток перевищив денний ліміт — нові входи блокуються."""
    if equity <= 0:
        return True
    return realized_pnl_today <= -abs(max_daily_loss_pct) * equity
