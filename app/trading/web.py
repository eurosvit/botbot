"""
HTTP-ендпоінти для моніторингу торгівлі (read-only).
Реєструється як Flask Blueprint у app/main.py.

  GET  /trading/dashboard   — веб-дашборд: крива капіталу + угоди
  GET  /trading/status      — поточний капітал, відкриті позиції, PnL за сьогодні
  GET  /trading/equity.json — точки кривої капіталу (для графіка)
  GET  /trading/trades.json — останні закриті угоди (для таблиці)
  POST /trading/run         — виконати один прохід циклу вручну (зручно для крону)

Усі ендпоінти приймають ?mode=paper|live (за замовч. — поточний TRADE_MODE).
"""
from __future__ import annotations

import logging
import os

from flask import Blueprint, Response, jsonify, request

from sqlalchemy import text

from app.db import get_engine
from ._dashboard import DASHBOARD_HTML
from .config import TradingConfig
from . import store


def _mode() -> str:
    """Режим для перегляду: з ?mode=… або поточний TRADE_MODE."""
    m = (request.args.get("mode") or "").strip().lower()
    return m if m in ("paper", "live", "backtest") else TradingConfig.from_env().mode

log = logging.getLogger(__name__)
bp = Blueprint("trading", __name__, url_prefix="/trading")


@bp.route("/status", methods=["GET"])
def status():
    try:
        cfg = TradingConfig.from_env()
        mode = _mode()
        store.migrate_trading()
        eng = get_engine()
        with eng.begin() as c:
            positions = c.execute(text("""
                SELECT symbol, side, qty, entry_price, stop_loss, take_profit, opened_at
                  FROM trade_positions
                 WHERE status='open' AND mode=:mode
                 ORDER BY opened_at
            """), {"mode": mode}).mappings().all()
            last_eq = c.execute(text("""
                SELECT equity, cash, open_positions, ts FROM trade_equity
                 WHERE mode=:mode ORDER BY ts DESC LIMIT 1
            """), {"mode": mode}).mappings().first()
            closed = c.execute(text("""
                SELECT COUNT(*) AS n, COALESCE(SUM(pnl),0) AS pnl
                  FROM trade_positions
                 WHERE status='closed' AND mode=:mode
            """), {"mode": mode}).mappings().first()

        return jsonify({
            "mode": mode,
            "exchange": cfg.exchange,
            "symbols": cfg.symbols,
            "timeframe": cfg.timeframe,
            "equity": float(last_eq["equity"]) if last_eq else None,
            "cash": float(last_eq["cash"]) if last_eq else None,
            "open_positions": [dict(p) for p in positions],
            "pnl_today": store.realized_pnl_today(mode),
            "closed_trades": int(closed["n"]),
            "total_realized_pnl": float(closed["pnl"]),
        })
    except Exception as e:
        log.exception("trading status error")
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/dashboard", methods=["GET"])
def dashboard():
    return Response(DASHBOARD_HTML, mimetype="text/html")


@bp.route("/equity.json", methods=["GET"])
def equity_json():
    try:
        store.migrate_trading()
        eng = get_engine()
        with eng.begin() as c:
            rows = c.execute(text("""
                SELECT ts, equity, cash, open_positions FROM trade_equity
                 WHERE mode=:mode ORDER BY ts DESC LIMIT 1000
            """), {"mode": _mode()}).mappings().all()
        # повертаємо у хронологічному порядку (для графіка)
        rows = list(reversed(rows))
        return jsonify([{
            "ts": r["ts"].isoformat(),
            "equity": float(r["equity"]),
            "cash": float(r["cash"]),
            "open_positions": int(r["open_positions"]),
        } for r in rows])
    except Exception as e:
        log.exception("equity.json error")
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/trades.json", methods=["GET"])
def trades_json():
    try:
        store.migrate_trading()
        eng = get_engine()
        with eng.begin() as c:
            rows = c.execute(text("""
                SELECT symbol, side, qty, entry_price, exit_price, pnl, pnl_pct,
                       reason_close, opened_at, closed_at
                  FROM trade_positions
                 WHERE status='closed' AND mode=:mode
                 ORDER BY closed_at DESC LIMIT 100
            """), {"mode": _mode()}).mappings().all()
        return jsonify([{
            "symbol": r["symbol"],
            "side": r["side"],
            "qty": float(r["qty"]),
            "entry_price": float(r["entry_price"]),
            "exit_price": float(r["exit_price"]) if r["exit_price"] is not None else None,
            "pnl": float(r["pnl"]) if r["pnl"] is not None else None,
            "pnl_pct": float(r["pnl_pct"]) if r["pnl_pct"] is not None else None,
            "reason_close": r["reason_close"],
            "closed_at": r["closed_at"].isoformat() if r["closed_at"] else None,
        } for r in rows])
    except Exception as e:
        log.exception("trades.json error")
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/check", methods=["GET"])
def check():
    """Швидка діагностика: чи доступні дані з біржі (тягне поточні ціни)."""
    from .market import Market
    try:
        cfg = TradingConfig.from_env()
        m = Market(cfg)
        prices = {}
        for s in cfg.symbols:
            try:
                prices[s] = m.last_price(s)
            except Exception as e:
                prices[s] = f"error: {str(e)[:160]}"
        ok = any(isinstance(v, (int, float)) for v in prices.values())
        return jsonify({
            "ok": ok,
            "exchange": cfg.exchange,
            "market_type": cfg.market_type,
            "timeframe": cfg.timeframe,
            "prices": prices,
        })
    except Exception as e:
        log.exception("check error")
        return jsonify({"ok": False, "message": str(e)}), 500


@bp.route("/optimize.json", methods=["GET"])
def optimize_json():
    """Запускає grid-search оптимізацію в браузері та повертає ТОП-комбінацій.

    Параметри запиту: symbol, strategy, candles, market_type, leverage, allow_shorts.
    Увага: тягне історію з біржі та проганяє багато бектестів — може зайняти час.
    """
    from dataclasses import replace
    from .market import Market
    from .backtest import fetch_history
    from .optimize import optimize as run_optimize
    try:
        base = TradingConfig.from_env()
        symbol = request.args.get("symbol") or base.symbols[0]
        strategy = (request.args.get("strategy") or base.strategy).strip().lower()
        candles_n = max(200, min(int(request.args.get("candles", 800)), 3000))
        overrides = {"mode": "backtest", "strategy": strategy}
        if request.args.get("market_type"):
            overrides["market_type"] = request.args["market_type"].strip().lower()
        if request.args.get("leverage"):
            overrides["leverage"] = int(request.args["leverage"])
        if request.args.get("allow_shorts"):
            overrides["allow_shorts"] = request.args["allow_shorts"].strip().lower() in ("1", "true", "yes", "on")
        cfg = replace(base, **overrides)

        market = Market(cfg)
        history = fetch_history(market, symbol, candles_n)
        if len(history) < 100:
            return jsonify({"status": "error", "message": f"мало історії: {len(history)}"}), 400
        results = run_optimize(cfg, symbol, history, top=15)

        def clean(r):
            sc = r["score"]
            return {
                "params": r["params"],
                "total_return_pct": round(r["total_return_pct"], 2),
                "buy_hold_return_pct": round(r["buy_hold_return_pct"], 2),
                "max_drawdown_pct": round(r["max_drawdown_pct"], 2),
                "win_rate": round(r["win_rate"], 1),
                "trades": r["trades"],
                "score": round(sc, 2) if sc not in (float("inf"), float("-inf")) else None,
            }
        return jsonify({
            "symbol": symbol, "strategy": strategy, "candles": len(history),
            "results": [clean(r) for r in results],
        })
    except Exception as e:
        log.exception("optimize.json error")
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/run", methods=["POST", "GET"])
def run_once():
    # Опційний захист: якщо задано TRADE_RUN_TOKEN — вимагаємо ?token=...
    expected = os.getenv("TRADE_RUN_TOKEN")
    if expected and request.args.get("token") != expected:
        return jsonify({"status": "error", "message": "unauthorized"}), 401
    try:
        from .engine import Engine
        cfg = TradingConfig.from_env()
        Engine(cfg).run_once()
        return jsonify({"status": "ok"})
    except Exception as e:
        log.exception("trading run error")
        return jsonify({"status": "error", "message": str(e)}), 500
