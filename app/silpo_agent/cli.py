"""Демо-CLI агента «Смарт-кошик Сільпо» (заявка на Silpo AI Factory).

Приклади:
    # перелік інструментів офіційного MCP «Сільпо» (tools/list)
    python -m app.silpo_agent.cli --list-tools

    # прямий виклик одного інструмента (tools/call) без LLM
    python -m app.silpo_agent.cli --call searchProducts --args '{"query": "борщ"}'

    # повний агентний сценарій
    python -m app.silpo_agent.cli "Збери кошик для борщу на 6 осіб до 800 грн"

    # персоналізація
    python -m app.silpo_agent.cli --watch-add "Сир Комо козиний" --ban-brand "БрендХ"
    python -m app.silpo_agent.cli --check-watchlist --telegram
    python -m app.silpo_agent.cli --savings
    python -m app.silpo_agent.cli --novelties --read-only

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

    prefs_group = parser.add_argument_group("персональні преференції")
    prefs_group.add_argument("--prefs", action="store_true",
                             help="показати збережені преференції і вийти")
    prefs_group.add_argument("--watch-add", metavar="ITEM",
                             help="додати товар у список відстеження")
    prefs_group.add_argument("--watch-remove", metavar="ITEM",
                             help="прибрати товар зі списку відстеження")
    prefs_group.add_argument("--ban-brand", metavar="BRAND",
                             help="додати бренд у стоп-лист (ніколи не пропонувати)")
    prefs_group.add_argument("--unban-brand", metavar="BRAND",
                             help="прибрати бренд зі стоп-листа")
    prefs_group.add_argument("--hide-np", action="store_true",
                             help="ховати товари з доставкою лише Новою Поштою")
    prefs_group.add_argument("--show-np", action="store_true",
                             help="знову показувати товари з доставкою НП")

    scen_group = parser.add_argument_group("готові сценарії")
    scen_group.add_argument("--check-watchlist", action="store_true",
                            help="перевірити, чи повернулись товари з відстеження")
    scen_group.add_argument("--savings", action="store_true",
                            help="база частих покупок + де найбільша економія")
    scen_group.add_argument("--novelties", action="store_true",
                            help="огляд новинок асортименту")
    scen_group.add_argument("--bonus-plan", action="store_true",
                            help="максимум балабонусів vs знижки для кошика")
    scen_group.add_argument("--slots", action="store_true",
                            help="найранніший доступний слот доставки")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    from app.silpo_agent import scenarios
    from app.silpo_agent.preferences import UserPrefs

    prefs = UserPrefs()
    prefs_changed = False
    if args.watch_add:
        prefs.watch(args.watch_add); prefs_changed = True
    if args.watch_remove:
        prefs.unwatch(args.watch_remove); prefs_changed = True
    if args.ban_brand:
        prefs.ban_brand(args.ban_brand); prefs_changed = True
    if args.unban_brand:
        prefs.unban_brand(args.unban_brand); prefs_changed = True
    if args.hide_np:
        prefs.data["hide_np_only"] = True; prefs.save(); prefs_changed = True
    if args.show_np:
        prefs.data["hide_np_only"] = False; prefs.save(); prefs_changed = True
    if args.prefs or prefs_changed:
        print(json.dumps(prefs.data, ensure_ascii=False, indent=2))
        if not any([args.check_watchlist, args.savings, args.novelties,
                    args.bonus_plan, args.slots]) and args.request == DEMO_REQUEST:
            return 0

    # Готові сценарії підмінюють запит користувача.
    if args.check_watchlist:
        args.request = scenarios.watchlist_check(prefs)
    elif args.savings:
        args.request = scenarios.savings_report()
    elif args.novelties:
        args.request = scenarios.novelties()
    elif args.bonus_plan:
        args.request = scenarios.bonus_optimizer()
    elif args.slots:
        args.request = scenarios.earliest_slot()

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
        prefs=prefs,
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
