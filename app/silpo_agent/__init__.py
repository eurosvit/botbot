"""Silpo AI Factory: агент «Смарт-кошик» поверх офіційного MCP «Сільпо».

Модулі:
- mcp_client: мінімальний клієнт MCP Streamable HTTP для https://mcp.silpo.ua/mcp
- agent:      агентний цикл на Claude (Anthropic SDK), який викликає MCP-інструменти
- cli:        демо-запуск із терміналу
"""

from app.silpo_agent.mcp_client import SilpoMCPClient  # noqa: F401
