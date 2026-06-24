UAH E-com Analytics v6 final

## Торговий модуль (MVP)

Додано автоматичний торговий бот для крипти (`app/trading`). Безпечний за
замовчуванням: paper-режим (реальні ціни, віртуальні гроші). Деталі, параметри
та порядок запуску — у [`docs/TRADING.md`](docs/TRADING.md).

```bash
python -m app.trading.backtest BTC/USDT   # перевірка стратегії на історії
python -m app.trading.runner              # paper-режим (за замовчуванням)
```
