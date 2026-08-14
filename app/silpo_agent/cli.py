"""Демо-CLI агента «Смарт-кошик Сільпо» (заявка на Silpo AI Factory).

Приклади:
    # перелік інструментів офіційного MCP «Сільпо» (tools/list)
    python -m app.silpo_agent.cli --list-tools

    # прямий виклик одного інструмента (tools/call) без LLM
    python -m app.silpo_agent.cli --call searchProducts --args '{"query": "борщ"}'

    # повний агентний сценарій
    python -m app.silpo_agent.cli "Збери кошик для борщу на 6 осіб до 800 грн"

Потрібні env-змінні: ANTHROPIC_API_KEY (для агента), SILPO_MCP_TOKEN
(якщо сервер вимагає авторизацію; токен видається після реєстрації).
"""

import argparse
import json
import logging
import sys

from app.silpo_agent.mcp_client import SilpoMCPClient

DEMO_REQUEST = "Збери кошик для борщу на 6 осіб, бюджет до 800 грн."


def main(argv=None):
    parser = argparse.ArgumentParser(description="Смарт-кошик Сільпо (MCP + Claude)")
    parser.add_argument("request", nargs="?", default=DEMO_REQUEST,
                        help="запит користувача природною мовою")
    parser.add_argument("--list-tools", action="store_true",
                        help="показати tools/list MCP-сервера і вийти")
    parser.add_argument("--call", metavar="TOOL",
                        help="викликати один інструмент напряму (tools/call)")
    parser.add_argument("--args", default="{}",
                        help="JSON-аргументи для --call")
    parser.add_argument("--telegram", action="store_true",
                        help="надіслати фінальну відповідь у Telegram")
    parser.add_argument("--read-only", action="store_true",
                        help="заборонити write-дії (кошик, доставка, бонуси)")
    parser.add_argument("--yes", action="store_true",
                        help="автопідтвердження write-дій (для демо/CI)")
    parser.add_argument("--audit", metavar="FILE",
                        help="писати аудит-лог викликів у файл (JSON lines)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    mcp = SilpoMCPClient()

    if args.list_tools:
        tools = mcp.list_tools()
        print(f"Інструментів на {mcp.endpoint}: {len(tools)}\n")
        for tool in tools:
            print(f"- {tool['name']}: {tool.get('description', '')[:120]}")
        return 0

    if args.call:
        result = mcp.call_tool(args.call, json.loads(args.args))
        print(result)
        return 0

    from app.silpo_agent.agent import SilpoAgent  # import тут: потребує anthropic
    from app.silpo_agent.guardrails import AuditLog

    def show_tool_call(name, tool_input, result):
        print(f"→ {name}({json.dumps(tool_input, ensure_ascii=False)})")
        print(f"  {result[:200].replace(chr(10), ' ')}…")

    def confirm_write(name, tool_input):
        if args.yes:
            return True
        prompt = (f"⚠ Агент хоче виконати write-дію: {name}"
                  f"({json.dumps(tool_input, ensure_ascii=False)}). Дозволити? [y/N] ")
        return input(prompt).strip().lower() in ("y", "yes", "так", "т")

    agent = SilpoAgent(
        mcp_client=mcp,
        confirm_write=confirm_write,
        read_only=args.read_only,
        audit=AuditLog(path=args.audit),
    )
    answer = agent.run(args.request, on_tool_call=show_tool_call)
    print("\n" + "=" * 60)
    print(answer)

    if args.telegram:
        from app.telegram import Telegram
        Telegram().send(answer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
