"""
Точка входу для торгового воркера.

  python -m app.trading.runner            # безкінечний цикл (paper за замовчуванням)
  python -m app.trading.runner once       # один прохід і вихід (зручно для крону)

Для деплою на Render додай у Procfile окремий процес-воркер (див. README).
"""
import logging
import sys

from app.logging_conf import configure_logging
from .config import TradingConfig
from .engine import Engine


def main():
    configure_logging()
    log = logging.getLogger("trading.runner")
    cfg = TradingConfig.from_env()
    try:
        cfg.validate()
    except Exception as e:
        log.error("Некоректна конфігурація: %s", e)
        sys.exit(1)

    if cfg.mode == "live":
        log.warning("⚠️  LIVE-РЕЖИМ: угоди виконуються РЕАЛЬНИМИ коштами!")

    engine = Engine(cfg)
    if len(sys.argv) > 1 and sys.argv[1] == "once":
        engine.run_once()
    else:
        engine.run_forever()


if __name__ == "__main__":
    main()
