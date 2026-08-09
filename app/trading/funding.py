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

# Стандартний інтервал funding у більшості бірж — 8 годин (3 рази на добу).
FUNDING_INTERVAL_HOURS = 8
INTERVALS_PER_YEAR = (24 / FUNDING_INTERVAL_HOURS) * 365  # = 1095

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


def simulate_carry(rates: list[float], fee_rate: float) -> dict:
    """Чиста математика cash-and-carry за наявними ставками funding.

    rates — список ставок funding за інтервал (частка, напр. 0.0001 = 0.01%/8год),
            з боку ШОРТА (додатна ставка = дохід шорта).
    fee_rate — комісія біржі на одну ногу однієї операції.

    Комісії: відкриття = 2 ноги (спот buy + perp short), закриття = 2 ноги →
    разом 4 × fee_rate від notional (одноразово за весь період утримання).
    """
    n = len(rates)
    if n == 0:
        return {"intervals": 0, "reason": "немає даних funding"}
    total = sum(rates)
    avg = total / n
    positive = sum(1 for r in rates if r > 0)
    round_trip_fee = 4 * fee_rate                     # частка notional
    window_days = n * FUNDING_INTERVAL_HOURS / 24
    return {
        "intervals": n,
        "window_days": round(window_days, 1),
        "avg_rate_pct": avg * 100,                    # середня ставка за 8 год, %
        "positive_share_pct": positive / n * 100,     # частка інтервалів зі ставкою > 0
        "apr_gross_pct": avg * INTERVALS_PER_YEAR * 100,        # річна дохідність до комісій
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
            res = simulate_carry(rates, fee_rate)
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
