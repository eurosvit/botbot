import logging
from datetime import date

logger = logging.getLogger(__name__)

def process_salesdrive_webhook(data=None):
    """
    Приймає payload із SalesDrive (list/dict із замовленнями за день).
    Повертає агрегований звіт: усі замовлення, реальні замовлення, замовлення в обробці,
    деталі по товарах, сума, джерело.
    """
    logger.info("Processing SalesDrive webhook")
    logger.debug(f"Payload: {data}")

    # Перевірка формату payload
    if not data or "orders" not in data:
        logger.error("No 'orders' in payload")
        return {"status": "error", "message": "Payload must include 'orders'."}

    orders = data["orders"]  # orders: list[dict]
    processed_orders = []
    pending_orders = []
    total_amount = 0.0
    processed_amount = 0.0
    pending_amount = 0.0

    # Джерела для агрегації
    sources = {}
    items = {}

    for order in orders:
        order_id = order.get("order_id")
        status = order.get("status")  # напр. "new", "processing", "completed", "sold"
        source = order.get("source")  # напр. "site", "instagram", "phone"
        amount = float(order.get("amount", 0.0))
        product_items = order.get("items", [])  # list[dict], кожен dict: {name, qty, price}

        total_amount += amount
        sources[source] = sources.get(source, 0) + 1

        # Агрегація товарів
        for item in product_items:
            name = item.get("name")
            qty = int(item.get("qty", 1))
            items[name] = items.get(name, 0) + qty

        # Визначаємо статус
        if status in ("sold", "completed"):  # реальні замовлення
            processed_orders.append(order)
            processed_amount += amount
        elif status in ("new", "processing", "pending"):
            pending_orders.append(order)
            pending_amount += amount

    real_count = len(processed_orders)
    pending_count = len(pending_orders)
    total_count = len(orders)

    # Формуємо звіт
    report = {
        "date": str(date.today()),
        "total_orders": total_count,
        "real_orders": real_count,
        "pending_orders": pending_count,
        "total_amount": total_amount,
        "real_amount": processed_amount,
        "pending_amount": pending_amount,
        "sources": sources,    # {"site": 5, "instagram": 2, ...}
        "items": items,        # {"Товар А": 10, "Товар Б": 2, ...}
        "orders_details": [
            {
                "order_id": o.get("order_id"),
                "status": o.get("status"),
                "source": o.get("source"),
                "amount": o.get("amount"),
                "items": o.get("items"),
            }
            for o in orders
        ],
    }

    logger.info(f"SalesDrive orders summary: {report}")
    return report
