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


def _days() -> int | None:
    """Фільтр періоду в днях (?days=7). None/0 — весь час."""
    try:
        d = int(request.args.get("days", "0"))
        return d if d > 0 else None
    except (TypeError, ValueError):
        return None

log = logging.getLogger(__name__)
bp = Blueprint("trading", __name__, url_prefix="/trading")


@bp.route("/status", methods=["GET"])
def status():
    try:
        from .tuner import apply_overrides
        from app.utils import utcnow
        cfg = apply_overrides(TradingConfig.from_env())  # фактична конфігурація (з autotune)
        mode = _mode()
        days = _days()
        store.migrate_trading()
        eng = get_engine()
        params = {"mode": mode}
        day_flt = ""
        if days:
            day_flt = " AND closed_at >= NOW() - make_interval(days => :d)"
            params["d"] = days
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
            closed = c.execute(text(f"""
                SELECT COUNT(*) AS n, COALESCE(SUM(pnl),0) AS pnl,
                       COALESCE(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END),0) AS wins
                  FROM trade_positions
                 WHERE status='closed' AND mode=:mode{day_flt}
            """), params).mappings().first()

        last_ts = last_eq["ts"] if last_eq else None
        secs_since = int((utcnow() - last_ts).total_seconds()) if last_ts else None
        return jsonify({
            "mode": mode,
            "exchange": cfg.exchange,
            "symbols": cfg.symbols,
            "timeframe": cfg.timeframe,
            # Фактична конфігурація (враховує авто-тюнінг):
            "strategy": cfg.strategy,
            "allow_shorts": cfg.allow_shorts,
            "trend_filter": cfg.use_trend_filter,
            "trend_ema": cfg.trend_ema,
            "auto_overrides": store.get_overrides(),
            # Живучість циклу:
            "last_run": last_ts.isoformat() if last_ts else None,
            "seconds_since_last_run": secs_since,
            "scanning": secs_since is not None and secs_since < 600,
            # Капітал і угоди:
            "equity": float(last_eq["equity"]) if last_eq else None,
            "cash": float(last_eq["cash"]) if last_eq else None,
            "open_positions": [dict(p) for p in positions],
            "pnl_today": store.realized_pnl_today(mode),
            "closed_trades": int(closed["n"]),
            "wins": int(closed["wins"]),
            "win_rate": round(int(closed["wins"]) / int(closed["n"]) * 100, 1) if int(closed["n"]) else None,
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
        days = _days()
        # Знімки пишуться щохвилини — агрегуємо в бакети, щоб крива була читабельна
        # й реально залежала від періоду (інакше LIMIT показує лише останні години).
        sec = 300 if (days and days <= 1) else 1800 if (days and days <= 7) \
            else 14400 if (days and days <= 30) else 7200
        params = {"mode": _mode(), "sec": sec}
        flt = ""
        if days:
            flt = " AND ts >= NOW() - make_interval(days => :d)"
            params["d"] = days
        with eng.begin() as c:
            rows = c.execute(text(f"""
                SELECT to_timestamp(floor(extract(epoch from ts)/:sec)*:sec) AS ts,
                       AVG(equity) AS equity, AVG(cash) AS cash,
                       MAX(open_positions) AS open_positions
                  FROM trade_equity
                 WHERE mode=:mode{flt}
                 GROUP BY 1 ORDER BY 1
            """), params).mappings().all()
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
        params = {"mode": _mode()}
        flt = ""
        if _days():
            flt = " AND closed_at >= NOW() - make_interval(days => :d)"
            params["d"] = _days()
        with eng.begin() as c:
            rows = c.execute(text(f"""
                SELECT symbol, side, qty, entry_price, exit_price, pnl, pnl_pct, fee,
                       reason_close, opened_at, closed_at
                  FROM trade_positions
                 WHERE status='closed' AND mode=:mode{flt}
                 ORDER BY closed_at DESC LIMIT 200
            """), params).mappings().all()
        return jsonify([{
            "symbol": r["symbol"],
            "side": r["side"],
            "qty": float(r["qty"]),
            "entry_price": float(r["entry_price"]),
            "exit_price": float(r["exit_price"]) if r["exit_price"] is not None else None,
            "pnl": float(r["pnl"]) if r["pnl"] is not None else None,
            "pnl_pct": float(r["pnl_pct"]) if r["pnl_pct"] is not None else None,
            "fee": float(r["fee"]) if r["fee"] is not None else 0.0,
            "reason_close": r["reason_close"],
            "closed_at": r["closed_at"].isoformat() if r["closed_at"] else None,
        } for r in rows])
    except Exception as e:
        log.exception("trades.json error")
        return jsonify({"status": "error", "message": str(e)}), 500


def format_daily_summary(stats: dict, cfg: TradingConfig, day: str) -> str:
    """Текст щоденного підсумку для Telegram."""
    eq = stats["equity"]
    ret = f"{(eq / cfg.paper_balance - 1) * 100:+.2f}%" if eq else "—"
    cash = f"{stats['cash']:.2f}" if stats["cash"] is not None else "—"
    eq_s = f"{eq:.2f}" if eq is not None else "—"
    today_line = f"📈 Сьогодні: {stats['trades_today']} угод, PnL <b>{stats['pnl_today']:+.2f}</b>"
    if stats["trades_today"]:
        today_line += f" ({stats['wins_today']} прибуткових)"
    return (
        f"📊 <b>Підсумок дня</b> — {day}\n"
        f"Режим: {cfg.mode} · {cfg.exchange} · {cfg.timeframe}\n"
        f"——————————————\n"
        f"💰 Капітал: <b>{eq_s}</b> {cfg.quote_currency} ({ret})\n"
        f"   готівка: {cash}\n"
        f"{today_line}\n"
        f"📌 Відкритих позицій: {stats['open_positions']}\n"
        f"Σ Усього: {stats['trades_total']} угод, реалізований PnL {stats['pnl_total']:+.2f}"
    )


@bp.route("/daily-summary", methods=["GET", "POST"])
def daily_summary():
    """Надсилає щоденний підсумок у Telegram. Підключи до денного крону (cron-job.org)."""
    expected = os.getenv("TRADE_RUN_TOKEN")
    if expected and request.args.get("token") != expected:
        return jsonify({"status": "error", "message": "unauthorized"}), 401
    from datetime import datetime, timezone
    from .notify import Notifier
    try:
        cfg = TradingConfig.from_env()
        store.migrate_trading()
        stats = store.daily_stats(cfg.mode)
        day = datetime.now(timezone.utc).strftime("%d.%m.%Y")
        msg = format_daily_summary(stats, cfg, day)
        sent = False
        n = Notifier(enabled=True)
        if n.tg is not None:
            n.send(msg)
            sent = True
        return jsonify({"ok": True, "sent": sent, "stats": stats})
    except Exception as e:
        log.exception("daily-summary error")
        return jsonify({"ok": False, "message": str(e)}), 500


@bp.route("/pin", methods=["GET", "POST"])
def pin():
    """Закріпити стратегію вручну й вимкнути autotune. Напр. /trading/pin?strategy=macd"""
    from .strategy import STRATEGIES
    strategy = (request.args.get("strategy") or "macd").strip().lower()
    if strategy not in STRATEGIES:
        return jsonify({"ok": False, "message": f"невідома стратегія (є: {', '.join(STRATEGIES)})"}), 400
    try:
        store.migrate_trading()
        store.clear_overrides()                       # прибрати авто-підібрані параметри
        store.delete_config("_autotune_off")          # прибрати старий маркер
        store.save_overrides({"strategy": strategy, "_pinned_strategy": strategy})
        return jsonify({"ok": True, "pinned_strategy": strategy,
                        "autotune": "оптимізує лише цю стратегію"})
    except Exception as e:
        log.exception("pin error")
        return jsonify({"ok": False, "message": str(e)}), 500


@bp.route("/unpin", methods=["GET", "POST"])
def unpin():
    """Зняти закріплення й знову ввімкнути autotune."""
    try:
        store.migrate_trading()
        store.clear_overrides()
        store.delete_config("_autotune_off")
        store.delete_config("_pinned_strategy")
        return jsonify({"ok": True, "autotune": "вільний вибір стратегії"})
    except Exception as e:
        log.exception("unpin error")
        return jsonify({"ok": False, "message": str(e)}), 500


@bp.route("/autotune", methods=["GET", "POST"])
def autotune_route():
    """Авто-тюнінг: підбирає й застосовує кращу конфігурацію на свіжих даних."""
    expected = os.getenv("TRADE_RUN_TOKEN")
    if expected and request.args.get("token") != expected:
        return jsonify({"status": "error", "message": "unauthorized"}), 401
    from .tuner import autotune, format_autotune
    from .notify import Notifier
    try:
        store.migrate_trading()
        cfg = TradingConfig.from_env()
        result = autotune(cfg, lock_strategy=store.pinned_strategy())
        Notifier(enabled=True).send(format_autotune(result))
        return jsonify(result)
    except Exception as e:
        log.exception("autotune error")
        return jsonify({"applied": False, "message": str(e)}), 500


@bp.route("/review", methods=["GET", "POST"])
def review_route():
    """Само-аналіз: розбір результатів у Telegram."""
    expected = os.getenv("TRADE_RUN_TOKEN")
    if expected and request.args.get("token") != expected:
        return jsonify({"status": "error", "message": "unauthorized"}), 401
    from .tuner import performance_review
    from .notify import Notifier
    try:
        store.migrate_trading()
        cfg = TradingConfig.from_env()
        msg = performance_review(cfg.mode)
        sent = Notifier(enabled=True)
        if sent.tg is not None:
            sent.send(msg)
        return jsonify({"ok": True, "review": msg})
    except Exception as e:
        log.exception("review error")
        return jsonify({"ok": False, "message": str(e)}), 500


@bp.route("/test-notify", methods=["GET"])
def test_notify():
    """Надсилає тестове повідомлення в Telegram — перевірка налаштувань сповіщень."""
    from .notify import Notifier
    try:
        n = Notifier(enabled=True)
        if n.tg is None:
            return jsonify({"ok": False,
                            "message": "Telegram не налаштований — перевір TG_BOT_TOKEN і TG_CHAT_ID"}), 400
        n.send("✅ Торговий бот на зв'язку. Сповіщення працюють.")
        return jsonify({"ok": True, "message": "повідомлення надіслано"})
    except Exception as e:
        log.exception("test-notify error")
        return jsonify({"ok": False, "message": str(e)}), 500


@bp.route("/signals", methods=["GET"])
def signals():
    """Діагностика: жива «думка» стратегії по кожній парі (чому входить / не входить)."""
    from .market import Market
    from .strategy import make_strategy, trend_direction, entry_allowed
    from .tuner import apply_overrides
    try:
        cfg = apply_overrides(TradingConfig.from_env())  # враховуємо авто-параметри
        m = Market(cfg)
        strat = make_strategy(cfg)
        out = []
        for s in cfg.symbols:
            try:
                candles = m.fetch_ohlcv(s)
                closed = candles[:-1]
                sig = strat.evaluate(closed)
                trend = trend_direction(cfg, [c[4] for c in closed])[-1]
                side = "long" if sig.action == "buy" else (
                    "short" if sig.action == "sell" and cfg.allow_shorts else None)
                blocked = bool(side) and not entry_allowed(cfg, trend, side)
                out.append({
                    "symbol": s,
                    "action": sig.action,
                    "reason": sig.reason,
                    "price": round(sig.price, 4) if sig.price else None,
                    "rsi": round(sig.rsi, 1) if sig.rsi is not None else None,
                    "trend": trend,
                    "entry_blocked_by_trend": blocked,
                })
            except Exception as e:
                out.append({"symbol": s, "error": str(e)[:160]})
        return jsonify({"strategy": cfg.strategy, "timeframe": cfg.timeframe,
                        "trend_filter": cfg.use_trend_filter, "trend_ema": cfg.trend_ema,
                        "allow_shorts": cfg.allow_shorts, "signals": out})
    except Exception as e:
        log.exception("signals error")
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
