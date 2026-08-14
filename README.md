UAH E-com Analytics v6 final

## Silpo AI Factory: агент «Смарт-кошик» (хакатон)

Заявка на хакатон «Сільпо AI Factory»: AI-агент, що збирає кошик покупок
через офіційний MCP «Сільпо» (`app/silpo_agent`). Деталі, вимоги конкурсу
та запуск демо — у [`docs/SILPO_HACKATHON.md`](docs/SILPO_HACKATHON.md).

```bash
python -m app.silpo_agent.cli --list-tools
python -m app.silpo_agent.cli "Збери кошик для борщу на 6 осіб до 800 грн"
```

## Торговий модуль (MVP)

Додано автоматичний торговий бот для крипти (`app/trading`). Безпечний за
замовчуванням: paper-режим (реальні ціни, віртуальні гроші). Деталі, параметри
та порядок запуску — у [`docs/TRADING.md`](docs/TRADING.md).

```bash
python -m app.trading.backtest BTC/USDT   # перевірка стратегії на історії
python -m app.trading.runner              # paper-режим (за замовчуванням)
```
