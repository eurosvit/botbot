"""Агент «Смарт-кошик Сільпо»: Claude + офіційний MCP «Сільпо».

Сценарій для хакатону Silpo AI Factory: користувач пише природною мовою
("зберу вечерю на 4 особи до 600 грн", "знайди інгредієнти для борщу"),
агент через MCP-інструменти Сільпо шукає товари (включно з пакетним пошуком
до 30 позицій і замінами відсутніх), збирає кошик і доводить до посилання
на чекаут.

Guardrails (див. guardrails.py): write-інструменти (кошик, доставка,
балабонуси, промокоди) виконуються лише після підтвердження користувача;
є read-only режим; усі виклики пишуться в аудит-лог.

Реалізовано ручним агентним циклом Anthropic Messages API, бо MCP-транспорт
у нас власний (SilpoMCPClient поверх requests). Схеми інструментів беруться
з tools/list і транслюються 1:1 у формат tools Anthropic API.
"""

import logging

import anthropic

from app.silpo_agent.guardrails import AuditLog, is_write_tool
from app.silpo_agent.mcp_client import MCPError, SilpoMCPClient

log = logging.getLogger(__name__)

MODEL = "claude-opus-5"
MAX_TOKENS = 16000
MAX_TURNS = 30

SYSTEM_PROMPT = """\
Ти — «Смарт-кошик Сільпо», асистент покупця мережі «Сільпо» (Україна).
Спілкуйся українською. Твоє завдання — з побутового запиту користувача
зібрати практичний кошик покупок, користуючись інструментами офіційного
MCP «Сільпо».

Як працювати з інструментами:
- Спершу з'ясуй з запиту страви/потреби та склади список інгредієнтів.
- Для списків використовуй пакетний пошук (до 30 товарів одним викликом),
  а не окремий виклик на кожну позицію.
- Якщо товару немає в наявності — скористайся інструментом підбору замін
  і чесно познач заміну у відповіді.
- Віддавай перевагу акційним позиціям, коли якість порівнянна; акції та
  добірки є в інструментах каталогу.
- Дотримуйся бюджету, якщо його вказано; якщо не вкладаєшся — запропонуй
  заміни та скажи, що прибрав.

Правила безпеки (важливо):
- Дії, що змінюють стан (додати в кошик, змінити доставку, застосувати
  промокод чи балабонуси, оформити замовлення), виконуй ЛИШЕ якщо
  користувач явно про це попросив. Балабонуси й купони ніколи не списуй
  за власною ініціативою.
- Кожна така дія проходить через підтвердження користувача. Якщо
  користувач відхилив дію — не повторюй її, запропонуй альтернативу.
- Нічого не оформлюй остаточно: доведи кошик до готовності та дай
  посилання на чекаут — фінальний клік за користувачем.

Економія та лояльність:
- Коли доречно, порівнюй два види вигоди в гривнях: економію від знижок
  та нарахування/списання балабонусів — і кажи, що вигідніше.
- Збираючи кошик з доставкою, одразу перевіряй найближчі тайм-слоти та
  пропонуй найранішній доступний.

У фінальній відповіді дай: список позицій (назва, ціна, кількість, позначки
акцій/замін), орієнтовну суму, посилання на чекаут (якщо кошик зібрано)
та 1-2 корисні поради. Не вигадуй товари й ціни — лише дані з інструментів;
якщо інструмент повернув помилку, скажи про це прямо.
"""

DECLINED_RESULT = (
    "Користувач НЕ підтвердив цю дію. Не повторюй її; запитай, "
    "що змінити, або запропонуй альтернативу."
)
READ_ONLY_RESULT = (
    "Дію заблоковано: агент працює в режимі read-only і не може змінювати "
    "кошик, доставку чи лояльність. Повідом про це користувача."
)


def mcp_tools_to_anthropic(tools):
    """Конвертує описи інструментів MCP (tools/list) у формат Anthropic API."""
    converted = []
    for tool in tools:
        converted.append(
            {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "input_schema": tool.get(
                    "inputSchema", {"type": "object", "properties": {}}
                ),
            }
        )
    return converted


class SilpoAgent:
    def __init__(self, mcp_client=None, anthropic_client=None, model=MODEL,
                 confirm_write=None, read_only=False, audit=None, prefs=None):
        """confirm_write(name, args) -> bool — підтвердження write-дій.

        Якщо колбек не задано, write-дії дозволені (зручно для тестів);
        read_only=True блокує їх повністю незалежно від колбека.
        prefs — UserPrefs: персональні преференції, додаються в промпт.
        """
        self.mcp = mcp_client or SilpoMCPClient()
        self.client = anthropic_client or anthropic.Anthropic()
        self.model = model
        self.system = SYSTEM_PROMPT
        if prefs is not None:
            block = prefs.render_for_prompt()
            if block:
                self.system = SYSTEM_PROMPT + "\n" + block + "\n"
        self.confirm_write = confirm_write
        self.read_only = read_only
        self.audit = audit or AuditLog()
        # Server-side fallback: якщо класифікатори Claude Opus 5 відхилять
        # запит, його автоматично повторить рекомендована fallback-модель.
        self._use_fallbacks = True

    def _create_message(self, messages, tools):
        if self._use_fallbacks:
            try:
                return self.client.beta.messages.create(
                    model=self.model,
                    max_tokens=MAX_TOKENS,
                    system=self.system,
                    tools=tools,
                    messages=messages,
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                )
            except anthropic.BadRequestError as e:
                # Бета може бути недоступна для акаунта — працюємо без неї.
                log.warning("Fallbacks unavailable, retrying without: %s", e)
                self._use_fallbacks = False
        return self.client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=self.system,
            tools=tools,
            messages=messages,
        )

    def _execute_tool(self, name, arguments, description=""):
        """Виконує інструмент з урахуванням guardrails.

        Повертає (текст_результату, is_error).
        """
        write = is_write_tool(name, description)
        if write and self.read_only:
            self.audit.record(name, arguments, write=True, allowed=False,
                              note="read-only mode")
            return READ_ONLY_RESULT, True
        if write and self.confirm_write and not self.confirm_write(name, arguments):
            self.audit.record(name, arguments, write=True, allowed=False,
                              note="declined by user")
            return DECLINED_RESULT, False
        try:
            result = self.mcp.call_tool(name, arguments)
            self.audit.record(name, arguments, write=write, allowed=True)
            return result, False
        except MCPError as e:
            self.audit.record(name, arguments, write=write, allowed=True,
                              note=f"error: {e}")
            return f"Помилка інструмента: {e}", True

    def run(self, user_request, on_tool_call=None):
        """Виконує запит користувача; повертає фінальний текст відповіді.

        on_tool_call(name, args, result) — необов'язковий колбек для логів/демо.
        """
        mcp_tools = self.mcp.list_tools()
        if not mcp_tools:
            raise MCPError("MCP-сервер не повернув жодного інструмента (tools/list)")
        descriptions = {t["name"]: t.get("description", "") for t in mcp_tools}
        tools = mcp_tools_to_anthropic(mcp_tools)
        messages = [{"role": "user", "content": user_request}]

        for _ in range(MAX_TURNS):
            response = self._create_message(messages, tools)

            if response.stop_reason == "refusal":
                return (
                    "Запит відхилено політиками безпеки моделі. "
                    "Спробуйте переформулювати."
                )

            if response.stop_reason != "tool_use":
                return "".join(
                    b.text for b in response.content if b.type == "text"
                )

            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                result, is_error = self._execute_tool(
                    block.name, block.input, descriptions.get(block.name, "")
                )
                if on_tool_call:
                    on_tool_call(block.name, block.input, result)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result[:50000],
                        "is_error": is_error,
                    }
                )
            messages.append({"role": "user", "content": tool_results})

        return "Перевищено ліміт кроків агента — спробуйте вужчий запит."
