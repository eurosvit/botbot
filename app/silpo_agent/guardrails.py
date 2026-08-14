"""Guardrails для агента: класифікація write-інструментів і аудит-лог.

MCP «Сільпо» віддає ~39 інструментів, частина з яких змінює стан
(кошик, доставка, промокоди, балабонуси). Документація не описує, хто
відповідає за помилкову дію агента, тому відповідальність беремо на себе
на рівні агента:

- write-інструменти виконуються лише після явного підтвердження користувача
  (або блокуються повністю в read-only режимі);
- кожен виклик інструмента пишеться в аудит-лог (хто, що, чи дозволено) —
  це і є відповідь на питання «хто натиснув кнопку».

Точних назв інструментів до отримання Starter Kit не знаємо, тому
класифікація евристична — за дієсловами у назві/описі. Евристика свідомо
консервативна: невідоме дієслово на початку назви вважаємо write.
"""

import json
import logging
import re
import time

log = logging.getLogger(__name__)

# Дієслова, що читають стан: такі інструменти безпечні за замовчуванням.
READ_VERBS = (
    "get", "list", "search", "find", "browse", "lookup", "check", "fetch",
    "view", "show", "suggest", "recommend", "batch",
)

# Дієслова, що змінюють стан: кошик, доставка, лояльність, замовлення.
WRITE_VERBS = (
    "add", "remove", "delete", "update", "set", "apply", "redeem", "use",
    "create", "place", "submit", "checkout", "clear", "cancel", "assign",
    "attach", "book", "reserve", "pay",
)

_CAMEL_SPLIT = re.compile(r"[^a-zA-Z]+|(?<=[a-z])(?=[A-Z])")


def _words(name):
    return [w.lower() for w in _CAMEL_SPLIT.split(name) if w]


def is_write_tool(name, description=""):
    """True, якщо інструмент схожий на такий, що змінює стан.

    Перевіряємо перше дієслово назви; якщо воно не з READ_VERBS —
    вважаємо write (консервативно), навіть якщо не з WRITE_VERBS.
    """
    words = _words(name)
    if not words:
        return True
    first = words[0]
    if first in WRITE_VERBS:
        return True
    if first in READ_VERBS:
        # Read-дієслово на початку, але write-дієслово далі ("getAndApply...")
        # все одно трактуємо як write.
        return any(w in WRITE_VERBS for w in words[1:])
    # Невідоме перше дієслово — консервативно вважаємо write.
    return True


class AuditLog:
    """Простий аудит-лог викликів інструментів (JSON lines у пам'яті/файл)."""

    def __init__(self, path=None):
        self.path = path
        self.entries = []

    def record(self, tool, arguments, *, write, allowed, note=""):
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "tool": tool,
            "arguments": arguments,
            "write": write,
            "allowed": allowed,
            "note": note,
        }
        self.entries.append(entry)
        line = json.dumps(entry, ensure_ascii=False)
        log.info("audit: %s", line)
        if self.path:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        return entry
