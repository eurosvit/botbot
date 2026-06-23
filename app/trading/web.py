"""
HTTP-ендпоінти для моніторингу торгівлі (read-only).
Реєструється як Flask Blueprint у app/main.py.

  GET /trading/status   — поточний капітал, відкриті позиції, PnL за сьогодні
  POST /trading/run     — виконати один прохід циклу вручну (зручно для крону)
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify

from sqlalchemy import text

from app.db import get_engine
from .config import TradingConfig
from . import store

log = logging.getLogger(__name__)
bp = Blueprint("trading", __name__, url_prefix="/trading")


@bp.route("/status", methods=["GET"])
def status():
    try:
        cfg = TradingConfig.from_env()
        store.migrate_trading()
        eng = get_engine()
        with eng.begin() as c:
            positions = c.execute(text("""
                SELECT symbol, side, qty, entry_price, stop_loss, take_profit, opened_at
                  FROM trade_positions
                 WHERE status='open' AND mode=:mode
                 ORDER BY opened_at
            """), {"mode": cfg.mode}).mappings().all()
            last_eq = c.execute(text("""
                SELECT equity, cash, open_positions, ts FROM trade_equity
                 WHERE mode=:mode ORDER BY ts DESC LIMIT 1
            """), {"mode": cfg.mode}).mappings().first()
            closed = c.execute(text("""
                SELECT COUNT(*) AS n, COALESCE(SUM(pnl),0) AS pnl
                  FROM trade_positions
                 WHERE status='closed' AND mode=:mode
            """), {"mode": cfg.mode}).mappings().first()

        return jsonify({
            "mode": cfg.mode,
            "exchange": cfg.exchange,
            "symbols": cfg.symbols,
            "timeframe": cfg.timeframe,
            "equity": float(last_eq["equity"]) if last_eq else None,
            "cash": float(last_eq["cash"]) if last_eq else None,
            "open_positions": [dict(p) for p in positions],
            "pnl_today": store.realized_pnl_today(cfg.mode),
            "closed_trades": int(closed["n"]),
            "total_realized_pnl": float(closed["pnl"]),
        })
    except Exception as e:
        log.exception("trading status error")
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/run", methods=["POST", "GET"])
def run_once():
    try:
        from .engine import Engine
        cfg = TradingConfig.from_env()
        Engine(cfg).run_once()
        return jsonify({"status": "ok"})
    except Exception as e:
        log.exception("trading run error")
        return jsonify({"status": "error", "message": str(e)}), 500
