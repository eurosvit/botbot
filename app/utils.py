from datetime import datetime, timezone

def utcnow():
    return datetime.now(timezone.utc)

def evaluate_signal(market_snapshot: dict) -> dict | None:
    price = market_snapshot.get("price")
    vol = market_snapshot.get("volume", 0)
    if price and vol > 0:
        return {"action": "LONG", "confidence": 0.6, "tp": price * 1.01, "sl": price * 0.99}
    return None
