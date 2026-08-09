"""
Фандинг-арбітраж (cash-and-carry) — ЧЕСНИЙ paper-експеримент.

Ідея (нейтральна до напряму ціни):
  * купуємо спот (long) і шортимо стільки ж у безстрокових ф'ючерсах (perp);
  * ціна нам байдужа — прибуток/збиток ніг взаємно гасяться (delta ≈ 0);
  * заробіток = funding, який лонги платять шортам (коли ставка > 0, шорт ОТРИМУЄ).

Тут лише АНАЛІЗ на реальних даних funding (без реальних угод):
  * fetch_funding_history — тягне історію ставок з ф'ючерсної біржі (ccxt);
  * simulate_carry — рахує чисту дохідність нейтральної позиції після комісій.

⚠️ Чесно: реальне виконання має більше витрат (спред, проковзування, керування
маржею шорта, ризик негативного funding). Це оцінка ЗВЕРХУ, орієнтир.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

# Інтервал funding РІЗНИЙ на біржах: Binance/Bybit/OKX — 8 год, Kraken — 1 год.
# Тому реальний інтервал визначаємо з дат історії, а це — лише запасний дефолт.
FUNDING_INTERVAL_HOURS = 8

# Кандидати «біржа → символ perp». Пробуємо по черзі, поки якась віддасть дані
# (Render має US-IP, тож набір підібрано з розрахунку на публічну доступність).
def _candidates(base: str) -> list[tuple[str, str]]:
    return [
        ("krakenfutures", f"{base}/USD:USD"),
        ("bybit",         f"{base}/USDT:USDT"),
        ("okx",           f"{base}/USDT:USDT"),
        ("gate",          f"{base}/USDT:USDT"),
        ("kucoinfutures", f"{base}/USDT:USDT"),
    ]


def simulate_carry(rates: list[float], fee_rate: float,
                   interval_hours: float = FUNDING_INTERVAL_HOURS) -> dict:
    """Чиста математика cash-and-carry за наявними ставками funding.

    rates — список ставок funding за інтервал (частка), з боку ШОРТА
            (додатна ставка = дохід шорта).
    fee_rate — комісія біржі на одну ногу однієї операції.
    interval_hours — період між виплатами funding (визначається з дат історії).

    Комісії: відкриття = 2 ноги (спот buy + perp short), закриття = 2 ноги →
    разом 4 × fee_rate від notional (одноразово за весь період утримання).
    """
    n = len(rates)
    if n == 0:
        return {"intervals": 0, "reason": "немає даних funding"}
    intervals_per_year = (24 / interval_hours) * 365
    total = sum(rates)
    avg = total / n
    positive = sum(1 for r in rates if r > 0)
    round_trip_fee = 4 * fee_rate                     # частка notional
    window_days = n * interval_hours / 24
    return {
        "intervals": n,
        "interval_hours": round(interval_hours, 2),
        "window_days": round(window_days, 1),
        "avg_rate_pct": avg * 100,                    # середня ставка за інтервал, %
        "positive_share_pct": positive / n * 100,     # частка інтервалів зі ставкою > 0
        "apr_gross_pct": avg * intervals_per_year * 100,       # річна дохідність до комісій
        "window_gross_pct": total * 100,               # накопичено за вікно (до комісій)
        "window_net_pct": (total - round_trip_fee) * 100,      # за вікно чистими (−4 ноги комісії)
        "round_trip_fee_pct": round_trip_fee * 100,
    }


def fetch_funding_history(base: str, fee_rate: float, days: int = 90) -> dict:
    """Тягне історію funding для base-активу з першої доступної біржі та рахує carry."""
    import ccxt
    from app.utils import utcnow

    since = int((utcnow().timestamp() - days * 86400) * 1000)
    errors = []
    for ex_name, symbol in _candidates(base):
        if not hasattr(ccxt, ex_name):
            continue
        try:
            client = getattr(ccxt, ex_name)({"enableRateLimit": True,
                                             "options": {"defaultType": "swap"}})
            hist = client.fetch_funding_rate_history(symbol, since=since, limit=1000)
            rates = [float(h["fundingRate"]) for h in hist if h.get("fundingRate") is not None]
            if len(rates) < 5:
                errors.append(f"{ex_name}: замало точок ({len(rates)})")
                continue
            # Реальний інтервал funding — з медіани відступів між датами (Kraken=1год, інші=8год).
            ts = [h["timestamp"] for h in hist if h.get("timestamp")]
            interval_hours = FUNDING_INTERVAL_HOURS
            if len(ts) >= 3:
                ts.sort()
                deltas = sorted(ts[i + 1] - ts[i] for i in range(len(ts) - 1))
                median_ms = deltas[len(deltas) // 2]
                if median_ms > 0:
                    interval_hours = min(24.0, max(0.5, median_ms / 3_600_000))
            res = simulate_carry(rates, fee_rate, interval_hours)
            res.update({"exchange": ex_name, "symbol": symbol, "base": base})
            try:
                res["current_rate_pct"] = float(
                    client.fetch_funding_rate(symbol)["fundingRate"]) * 100
            except Exception:
                res["current_rate_pct"] = res["avg_rate_pct"]
            return res
        except Exception as e:  # noqa: BLE001 — пробуємо наступну біржу
            errors.append(f"{ex_name}: {type(e).__name__}")
            continue
    return {"intervals": 0, "reason": "не вдалося отримати funding із жодної біржі",
            "tried": errors}
