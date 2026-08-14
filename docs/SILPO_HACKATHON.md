# Silpo AI Factory — заявка «Смарт-кошик Сільпо»

Прототип для хакатону [«Сільпо» AI Factory](https://ai-factory.silpo.ua/) —
AI-агент, що з побутового запиту («збери кошик для борщу на 6 осіб до
800 грн») формує реальний кошик покупок через офіційний
**MCP «Сільпо»** (`https://mcp.silpo.ua/mcp`).

## Ключові факти про конкурс

- **Призовий фонд:** 100 000 ₴
- **Реєстрація:** до **31 серпня** на https://ai-factory.silpo.ua/#register
  (після реєстрації видають доступ до документації MCP і Starter Kit)
- **Старт хакатону:** 1 вересня, 09:00
- **Вимоги до проєкту:**
  1. підключення до `https://mcp.silpo.ua/mcp`;
  2. виклик щонайменше одного інструмента з `tools/list` у робочому сценарії;
  3. робочий прототип/демо, яке показує цей виклик;
  4. токени зберігаються на сервері, а не в клієнтському коді.

## Ідея: «Смарт-кошик Сільпо»

Агент-покупець природною мовою: планування меню → пошук інгредієнтів →
порівняння акцій → готовий кошик із сумою та порадами. Технічно це
демонструє наскрізний ланцюжок *LLM ⇄ MCP «Сільпо»* і легко розширюється
(Telegram-бот уже є в цьому репозиторії).

## Архітектура

```
Користувач ──> app/silpo_agent/cli.py (або Telegram)
                      │
                      ▼
              SilpoAgent (Claude, модель claude-opus-5, агентний цикл tool use)
                      │  tools/list + tools/call
                      ▼
              SilpoMCPClient (MCP Streamable HTTP, JSON-RPC 2.0)
                      │  Authorization: Bearer $SILPO_MCP_TOKEN (server-side)
                      ▼
              https://mcp.silpo.ua/mcp
```

- `app/silpo_agent/mcp_client.py` — власний легкий MCP-клієнт на `requests`:
  initialize/initialized, `tools/list` (з пагінацією), `tools/call`,
  підтримка відповідей JSON і SSE, заголовок `Mcp-Session-Id`.
- `app/silpo_agent/agent.py` — агентний цикл на Anthropic SDK: схеми
  інструментів беруться з `tools/list` і передаються Claude, виклики
  виконуються через MCP, результати повертаються моделі до фінальної
  відповіді. Увімкнено server-side fallback (якщо запит відхилять
  класифікатори Claude Opus 5, його автоматично повторить резервна модель).
- `app/silpo_agent/cli.py` — демо: `--list-tools`, `--call`, повний сценарій,
  опційна відправка результату в Telegram.

## Запуск

```bash
pip install -r requirements.txt

export ANTHROPIC_API_KEY=...       # ключ Anthropic (лише на сервері)
export SILPO_MCP_TOKEN=...         # токен MCP «Сільпо» (видається після реєстрації)

# 1. Перевірка підключення: перелік інструментів
python -m app.silpo_agent.cli --list-tools

# 2. Прямий виклик інструмента без LLM (назву взяти з tools/list)
python -m app.silpo_agent.cli --call <toolName> --args '{"query": "борщ"}'

# 3. Повне демо
python -m app.silpo_agent.cli "Збери кошик для борщу на 6 осіб до 800 грн"

# Тести (без мережі, на моках)
python -m pytest tests/test_silpo_agent.py -v
```

> Локально MCP-сервер можна під'єднати й до Claude Code:
> `claude mcp add --transport http silpo https://mcp.silpo.ua/mcp`

## Чекліст до дедлайну

- [ ] Зареєструватися на ai-factory.silpo.ua **до 31.08**
- [ ] Отримати Starter Kit + токен, виконати `--list-tools` проти живого сервера
- [ ] Підігнати сценарій під реальні назви інструментів (пошук/акції/кошик/доставка)
- [ ] Записати демо (скрінкаст CLI або Telegram-бота)
- [ ] За бажанням: обгорнути в Telegram-бота на наявній інфраструктурі `app/`

## Джерела

- [ai-factory.silpo.ua](https://ai-factory.silpo.ua/) — офіційний сайт хакатону
- [Документація MCP «Сільпо»](https://ai-factory.silpo.ua/docs/mcp)
- [Анонс на dev.ua](https://dev.ua/news/silpo-ai-factory-1785848152)
- [Подія на DOU](https://dou.ua/calendar/58019/)
