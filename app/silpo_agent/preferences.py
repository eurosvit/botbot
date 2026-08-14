"""Персональні преференції користувача для агента «Смарт-кошик Сільпо».

Локальний JSON-профіль (за замовчуванням silpo_prefs.json, шлях можна
змінити через SILPO_PREFS_PATH). Зберігає те, чого немає в профілі Сільпо:

- watchlist:      улюблені товари, що зникли — відстежуємо повернення;
- banned_brands:  бренди, які ніколи не пропонувати;
- hide_np_only:   ховати товари, що доставляються лише Новою Поштою;
- goals:          довільні правила користувача (наприклад, «максимум
                  балабонусів», «завжди найранніший слот доставки»).

Преференції рендеряться текстовим блоком у системний промпт агента, тож
діють у будь-якому сценарії без окремої логіки під кожен пункт.
"""

import json
import os

DEFAULT_PATH = "silpo_prefs.json"

DEFAULTS = {
    "watchlist": [],
    "banned_brands": [],
    "hide_np_only": False,
    "goals": [],
}


class UserPrefs:
    def __init__(self, path=None):
        self.path = path or os.getenv("SILPO_PREFS_PATH", DEFAULT_PATH)
        self.data = dict(DEFAULTS)
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                stored = json.load(f)
            for key in DEFAULTS:
                if key in stored:
                    self.data[key] = stored[key]

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    # -- watchlist ---------------------------------------------------------

    def watch(self, item):
        if item not in self.data["watchlist"]:
            self.data["watchlist"].append(item)
            self.save()

    def unwatch(self, item):
        if item in self.data["watchlist"]:
            self.data["watchlist"].remove(item)
            self.save()

    # -- бренди ------------------------------------------------------------

    def ban_brand(self, brand):
        if brand not in self.data["banned_brands"]:
            self.data["banned_brands"].append(brand)
            self.save()

    def unban_brand(self, brand):
        if brand in self.data["banned_brands"]:
            self.data["banned_brands"].remove(brand)
            self.save()

    # -- рендер у промпт ---------------------------------------------------

    def render_for_prompt(self):
        """Текстовий блок преференцій для системного промпта агента."""
        lines = ["Персональні преференції користувача (обов'язкові до виконання):"]
        if self.data["banned_brands"]:
            lines.append(
                "- СТОП-БРЕНДИ: ніколи не пропонуй і не додавай у кошик товари "
                "брендів: " + ", ".join(self.data["banned_brands"]) + ". "
                "Якщо такий товар — єдиний варіант, скажи про це й запропонуй "
                "альтернативу."
            )
        if self.data["hide_np_only"]:
            lines.append(
                "- Не показуй товари, які доставляються лише Новою Поштою; "
                "працюй тільки з доставкою «Сільпо»."
            )
        if self.data["watchlist"]:
            lines.append(
                "- Список відстеження (улюблене, що зникало з продажу): "
                + ", ".join(self.data["watchlist"]) + ". Якщо під час роботи "
                "помічаєш, що щось із цього знову в наявності — обов'язково "
                "згадай про це у відповіді."
            )
        for goal in self.data["goals"]:
            lines.append(f"- {goal}")
        if len(lines) == 1:
            return ""
        return "\n".join(lines)
