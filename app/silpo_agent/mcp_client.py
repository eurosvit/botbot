"""Мінімальний MCP-клієнт (Streamable HTTP) для офіційного сервера «Сільпо».

Вимоги конкурсу Silpo AI Factory:
- підключення до https://mcp.silpo.ua/mcp;
- виклик щонайменше одного інструмента з tools/list у робочому сценарії;
- токени зберігаються на сервері (env-змінна SILPO_MCP_TOKEN), не в клієнтському коді.

Реалізовано JSON-RPC 2.0 поверх HTTP POST згідно зі специфікацією MCP
(Streamable HTTP transport, protocol 2025-06-18): initialize ->
notifications/initialized -> tools/list -> tools/call. Сервер може відповідати
як application/json, так і text/event-stream — обидва варіанти підтримано.
"""

import itertools
import json
import logging
import os

import requests

log = logging.getLogger(__name__)

DEFAULT_ENDPOINT = "https://mcp.silpo.ua/mcp"
PROTOCOL_VERSION = "2025-06-18"


class MCPError(RuntimeError):
    """Помилка рівня JSON-RPC або транспорту MCP."""

    def __init__(self, message, code=None, data=None):
        super().__init__(message)
        self.code = code
        self.data = data


class SilpoMCPClient:
    """Клієнт одного MCP-з'єднання (HTTP-сесія + Mcp-Session-Id)."""

    def __init__(self, endpoint=None, token=None, timeout=30):
        self.endpoint = endpoint or os.getenv("SILPO_MCP_ENDPOINT", DEFAULT_ENDPOINT)
        # Токен лише з середовища/секретів бекенду — ніколи не хардкодимо.
        self.token = token if token is not None else os.getenv("SILPO_MCP_TOKEN")
        self.timeout = timeout
        self.session_id = None
        self._ids = itertools.count(1)
        self._http = requests.Session()
        self._initialized = False

    # -- транспорт ---------------------------------------------------------

    def _headers(self):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": PROTOCOL_VERSION,
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        return headers

    @staticmethod
    def _parse_sse(text):
        """Дістає останнє JSON-повідомлення з відповіді text/event-stream."""
        message = None
        for line in text.splitlines():
            if line.startswith("data:"):
                payload = line[len("data:"):].strip()
                if payload:
                    message = json.loads(payload)
        if message is None:
            raise MCPError("Порожня SSE-відповідь від MCP-сервера")
        return message

    def _post(self, payload, expect_response=True):
        resp = self._http.post(
            self.endpoint, json=payload, headers=self._headers(), timeout=self.timeout
        )
        sid = resp.headers.get("Mcp-Session-Id")
        if sid:
            self.session_id = sid
        if resp.status_code in (401, 403):
            raise MCPError(
                f"MCP-сервер відхилив запит ({resp.status_code}). "
                "Перевірте SILPO_MCP_TOKEN (токен видається після реєстрації "
                "на ai-factory.silpo.ua)."
            )
        resp.raise_for_status()
        if not expect_response or resp.status_code == 202 or not resp.content:
            return None
        content_type = resp.headers.get("Content-Type", "")
        if "text/event-stream" in content_type:
            message = self._parse_sse(resp.text)
        else:
            message = resp.json()
        if "error" in message:
            err = message["error"]
            raise MCPError(
                err.get("message", "MCP error"),
                code=err.get("code"),
                data=err.get("data"),
            )
        return message.get("result")

    def _request(self, method, params=None):
        payload = {"jsonrpc": "2.0", "id": next(self._ids), "method": method}
        if params is not None:
            payload["params"] = params
        return self._post(payload)

    def _notify(self, method):
        self._post({"jsonrpc": "2.0", "method": method}, expect_response=False)

    # -- життєвий цикл MCP -------------------------------------------------

    def initialize(self):
        """Рукостискання initialize + notifications/initialized."""
        if self._initialized:
            return self._server_info
        result = self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "botbot-silpo-agent", "version": "1.0.0"},
            },
        )
        self._notify("notifications/initialized")
        self._initialized = True
        self._server_info = result or {}
        log.info("MCP initialized: %s", self._server_info.get("serverInfo"))
        return self._server_info

    def list_tools(self):
        """tools/list — перелік інструментів сервера (з пагінацією)."""
        self.initialize()
        tools, cursor = [], None
        while True:
            params = {"cursor": cursor} if cursor else None
            result = self._request("tools/list", params) or {}
            tools.extend(result.get("tools", []))
            cursor = result.get("nextCursor")
            if not cursor:
                return tools

    def call_tool(self, name, arguments=None):
        """tools/call — виклик інструмента; повертає текстовий вміст результату."""
        self.initialize()
        result = self._request(
            "tools/call", {"name": name, "arguments": arguments or {}}
        ) or {}
        if result.get("isError"):
            raise MCPError(f"Інструмент {name} повернув помилку: {result}")
        parts = []
        for block in result.get("content", []):
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
            else:
                parts.append(json.dumps(block, ensure_ascii=False))
        structured = result.get("structuredContent")
        if structured is not None and not parts:
            parts.append(json.dumps(structured, ensure_ascii=False))
        return "\n".join(parts) if parts else json.dumps(result, ensure_ascii=False)

    def close(self):
        self._http.close()
