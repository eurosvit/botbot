"""
Збереження стану торгівлі в Postgres (через існуючий app.db).
Позиції зберігаються в БД, тож стан переживає рестарти сервісу.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import text

from app.db import get_engine

log = logging.getLogger(__name__)


def migrate_trading() -> None:
    """Створює таблиці торгового модуля, якщо їх ще немає."""
    eng = get_engine()
    with eng.begin() as c:
        c.execute(text("""
            CREATE TABLE IF NOT EXISTS trade_positions (
                id SERIAL PRIMARY KEY,
                mode TEXT NOT NULL,
                exchange TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL DEFAULT 'long',
                qty NUMERIC NOT NULL,
                entry_price NUMERIC NOT NULL,
                stop_loss NUMERIC,
                take_profit NUMERIC,
                status TEXT NOT NULL DEFAULT 'open',
                exit_price NUMERIC,
                pnl NUMERIC,
                pnl_pct NUMERIC,
                reason_open TEXT,
                reason_close TEXT,
                opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                closed_at TIMESTAMPTZ
            )
        """))
        c.execute(text("CREATE INDEX IF NOT EXISTS idx_pos_status ON trade_positions(status)"))
        c.execute(text("CREATE INDEX IF NOT EXISTS idx_pos_symbol ON trade_positions(symbol)"))

        c.execute(text("""
            CREATE TABLE IF NOT EXISTS trade_equity (
                id SERIAL PRIMARY KEY,
                ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                mode TEXT NOT NULL,
                equity NUMERIC NOT NULL,
                cash NUMERIC NOT NULL,
                open_positions INTEGER NOT NULL DEFAULT 0
            )
        """))
        log.info("Trading migration completed.")


def open_position(p: dict) -> int:
    eng = get_engine()
    with eng.begin() as c:
        row = c.execute(text("""
            INSERT INTO trade_positions
                (mode, exchange, symbol, side, qty, entry_price, stop_loss, take_profit,
                 status, reason_open, opened_at)
            VALUES
                (:mode, :exchange, :symbol, :side, :qty, :entry_price, :stop_loss, :take_profit,
                 'open', :reason_open, :opened_at)
            RETURNING id
        """), p)
        return int(row.scalar_one())


def close_position(pos_id: int, exit_price: float, pnl: float, pnl_pct: float, reason: str) -> None:
    eng = get_engine()
    with eng.begin() as c:
        c.execute(text("""
            UPDATE trade_positions
               SET status='closed', exit_price=:exit_price, pnl=:pnl, pnl_pct=:pnl_pct,
                   reason_close=:reason, closed_at=:closed_at
             WHERE id=:id
        """), {
            "id": pos_id, "exit_price": exit_price, "pnl": pnl, "pnl_pct": pnl_pct,
            "reason": reason, "closed_at": datetime.now(timezone.utc),
        })


def open_positions(mode: str) -> list[dict]:
    eng = get_engine()
    with eng.begin() as c:
        rows = c.execute(text("""
            SELECT id, symbol, side, qty, entry_price, stop_loss, take_profit
              FROM trade_positions
             WHERE status='open' AND mode=:mode
        """), {"mode": mode}).mappings().all()
        return [dict(r) for r in rows]


def has_open_position(mode: str, symbol: str) -> bool:
    eng = get_engine()
    with eng.begin() as c:
        n = c.execute(text("""
            SELECT COUNT(*) FROM trade_positions
             WHERE status='open' AND mode=:mode AND symbol=:symbol
        """), {"mode": mode, "symbol": symbol}).scalar_one()
        return int(n) > 0


def snapshot_equity(mode: str, equity: float, cash: float, open_count: int) -> None:
    eng = get_engine()
    with eng.begin() as c:
        c.execute(text("""
            INSERT INTO trade_equity (mode, equity, cash, open_positions)
            VALUES (:mode, :equity, :cash, :open_count)
        """), {"mode": mode, "equity": equity, "cash": cash, "open_count": open_count})


def daily_stats(mode: str) -> dict:
    """Зведена статистика для щоденного підсумку."""
    eng = get_engine()
    with eng.begin() as c:
        last_eq = c.execute(text("""
            SELECT equity, cash FROM trade_equity
             WHERE mode=:mode ORDER BY ts DESC LIMIT 1
        """), {"mode": mode}).mappings().first()
        today = c.execute(text("""
            SELECT COUNT(*) AS n, COALESCE(SUM(pnl), 0) AS pnl,
                   COALESCE(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END), 0) AS wins
              FROM trade_positions
             WHERE status='closed' AND mode=:mode AND closed_at >= date_trunc('day', NOW())
        """), {"mode": mode}).mappings().first()
        total = c.execute(text("""
            SELECT COUNT(*) AS n, COALESCE(SUM(pnl), 0) AS pnl
              FROM trade_positions WHERE status='closed' AND mode=:mode
        """), {"mode": mode}).mappings().first()
        open_n = c.execute(text("""
            SELECT COUNT(*) FROM trade_positions WHERE status='open' AND mode=:mode
        """), {"mode": mode}).scalar_one()
    return {
        "equity": float(last_eq["equity"]) if last_eq else None,
        "cash": float(last_eq["cash"]) if last_eq else None,
        "trades_today": int(today["n"]),
        "pnl_today": float(today["pnl"]),
        "wins_today": int(today["wins"]),
        "open_positions": int(open_n),
        "trades_total": int(total["n"]),
        "pnl_total": float(total["pnl"]),
    }


def realized_pnl_total(mode: str) -> float:
    """Сума реалізованого PnL за всіма закритими угодами (для розрахунку балансу)."""
    eng = get_engine()
    with eng.begin() as c:
        v = c.execute(text("""
            SELECT COALESCE(SUM(pnl), 0) FROM trade_positions
             WHERE status='closed' AND mode=:mode
        """), {"mode": mode}).scalar_one()
        return float(v or 0.0)


def realized_pnl_today(mode: str) -> float:
    """Сума реалізованого PnL за сьогодні (для денного стоп-ліміту)."""
    eng = get_engine()
    with eng.begin() as c:
        v = c.execute(text("""
            SELECT COALESCE(SUM(pnl), 0) FROM trade_positions
             WHERE status='closed' AND mode=:mode
               AND closed_at >= date_trunc('day', NOW())
        """), {"mode": mode}).scalar_one()
        return float(v or 0.0)
