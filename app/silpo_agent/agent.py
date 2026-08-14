"""Агент «Смарт-кошик Сільпо»: Claude + офіційний MCP «Сільпо».

Сценарій для хакатону Silpo AI Factory: користувач пише природною мовою
("зберу вечерю на 4 особи до 600 грн", "знайди інгредієнти для борщу"),
агент через MCP-інструменти Сільпо шукає товари, порівнює акції та формує
готовий кошик зі списком і підсумковою вартістю.

Реалізовано ручним агентним циклом Anthropic Messages API, бо MCP-транспорт
у нас власний (SilpoMCPClient поверх requests). Схеми інструментів беруться
з tools/list і транслюються 1:1 у формат tools Anthropic API.
"""

import logging

import anthropic

from app.silpo_agent.mcp_client import MCPError, SilpoMCPClient

log = logging.getLogger(__name__)

MODEL = "claude-opus-5"
MAX_TOKENS = 16000
MAX_TURNS = 20

SYSTEM_PROMPT = """\
Ти — «Смарт-кошик Сільпо», асистент покупця мережі «Сільпо» (Україна).
Спілкуйся українською. Твоє завдання — з побутового запиту користувача
зібрати практичний кошик покупок, користуючись інструментами офіційного
MCP «Сільпо».

Правила роботи:
- Спершу з'ясуй з запиту страви/потреби та склади список інгредієнтів.
- Шукай реальні товари через інструменти MCP; віддавай перевагу акційним
  позиціям, коли якість порівнянна.
- Дотримуйся бюджету, якщо його вказано; якщо не вкладаєшся — запропонуй
  заміни та чесно скажи, що прибрав.
- У фінальній відповіді дай: список позицій (назва, ціна, кількість),
  орієнтовну суму та 1-2 корисні поради (акції, доставка).
- Не вигадуй товари й ціни — лише дані з інструментів. Якщо інструмент
  повернув помилку, скажи про це прямо.
"""


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
    def __init__(self, mcp_client=None, anthropic_client=None, model=MODEL):
        self.mcp = mcp_client or SilpoMCPClient()
        self.client = anthropic_client or anthropic.Anthropic()
        self.model = model
        # Server-side fallback: якщо класифікатори Claude Opus 5 відхилять
        # запит, його автоматично повторить рекомендована fallback-модель.
        self._use_fallbacks = True

    def _create_message(self, messages, tools):
        if self._use_fallbacks:
            try:
                return self.client.beta.messages.create(
                    model=self.model,
                    max_tokens=MAX_TOKENS,
                    system=SYSTEM_PROMPT,
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
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        )

    def run(self, user_request, on_tool_call=None):
        """Виконує запит користувача; повертає фінальний текст відповіді.

        on_tool_call(name, args, result) — необов'язковий колбек для логів/демо.
        """
        tools = mcp_tools_to_anthropic(self.mcp.list_tools())
        if not tools:
            raise MCPError("MCP-сервер не повернув жодного інструмента (tools/list)")
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
                try:
                    result = self.mcp.call_tool(block.name, block.input)
                    is_error = False
                except MCPError as e:
                    result = f"Помилка інструмента: {e}"
                    is_error = True
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
