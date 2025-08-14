import logging

logger = logging.getLogger(__name__)

def process_salesdrive_webhook(data=None):
    logger.info("Processing SalesDrive webhook inside module")
    logger.debug(f"Webhook payload: {data}")
    # Тут може бути твоя реальна логіка, зараз заглушка
    return {"msg": "SalesDrive webhook processed", "input": data}
