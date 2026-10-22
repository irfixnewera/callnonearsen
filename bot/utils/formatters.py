"""
Форматирование результатов анализа и дневника в красивый HTML.
"""

from bot.services.gemini_vision import FoodAnalysis, FoodItem
from bot.texts import (
    GOAL_EXACT,
    GOAL_LEFT,
    GOAL_NEAR,
    GOAL_OVER,
    GOAL_PROGRESS,
    LOW_CONFIDENCE_HINT,
    LOW_CONFIDENCE_ITEMS,
    RESULT_FOOTER,
    RESULT_HEADER,
)


def needs_clarification(analysis: FoodAnalysis) -> bool:
    """Уточняем только если ИИ явно не уверен (confidence=low)."""
    return any(i.confidence == "low" for i in analysis.items)


def low_confidence_names(analysis: FoodAnalysis) -> list[str]:
    return [i.name for i in analysis.items if i.confidence == "low"]


def format_goal_block(eaten: int, goal: int | None) -> str:
    """Блок прогресса по дневному лимиту. Пустая строка, если лимита нет."""
    if not goal or goal <= 0:
        return ""

    lines = [GOAL_PROGRESS.format(eaten=eaten, goal=goal)]
    left = goal - eaten

    if left > 150:
        lines.append(GOAL_LEFT.format(left=left))
    elif left > 0:
        lines.append(GOAL_NEAR)
        lines.append(GOAL_LEFT.format(left=left))
    elif left == 0:
        lines.append(GOAL_EXACT)
    else:
        lines.append(GOAL_OVER.format(over=abs(left)))

    return "\n".join(lines)


def format_food_result(
    analysis: FoodAnalysis,
    *,
    eaten_today: int = 0,
    goal: int | None = None,
    show_clarify_hint: bool = False,
) -> str:
    lines: list[str] = [RESULT_HEADER, ""]

    for item in analysis.items:
        conf = {
            "high": "",
            "medium": " · примерно",
            "low": " · не уверена",
        }.get(item.confidence, "")
        lines.append(
            f"<b>{item.name}</b> — {item.weight_grams} г{conf}\n"
            f"   {item.calories} ккал · "
            f"Б {item.protein} · Ж {item.fat} · У {item.carbs}"
        )
        lines.append("")

    total = analysis.total
    lines.append("─────────────")
    lines.append(
        f"<b>Итого:</b> {total.calories} ккал\n"
        f"Белки {total.protein} · Жиры {total.fat} · Углеводы {total.carbs}"
    )

    # Прогресс по лимиту (уже съеденное сегодня + это блюдо, если смотрим «как будет»)
    # Здесь eaten_today — уже записанное в дневник; блюдо ещё не добавлено
    if goal:
        lines.append("")
        projected = eaten_today + total.calories
        lines.append(format_goal_block(projected, goal))

    if analysis.comment:
        lines.append("")
        lines.append(f"<i>{analysis.comment}</i>")

    if show_clarify_hint:
        names = low_confidence_names(analysis)
        lines.append("")
        if names:
            lines.append(LOW_CONFIDENCE_ITEMS.format(items=", ".join(names)))
        lines.append(LOW_CONFIDENCE_HINT)
    else:
        lines.append("")
        lines.append(RESULT_FOOTER)

    return "\n".join(lines)


def format_diary_day(
    entries: list,
    totals: tuple[int, int, int, int],
    title: str,
    goal: int | None = None,
) -> str:
    cal, prot, fat, carbs = totals
    lines: list[str] = [f"<b>{title}</b>", ""]

    if not entries:
        lines.append("Пока пусто.")
        return "\n".join(lines)

    for entry in entries:
        time_str = entry.created_at.strftime("%H:%M")
        lines.append(f"• {time_str} — <b>{entry.calories}</b> ккал")
        if entry.comment:
            lines.append(f"  <i>{entry.comment}</i>")

    lines.append("")
    lines.append("─────────────")
    lines.append(
        f"<b>Итого:</b> {cal} ккал\n"
        f"Б {prot} · Ж {fat} · У {carbs}"
    )

    goal_block = format_goal_block(cal, goal)
    if goal_block:
        lines.append("")
        lines.append(goal_block)

    return "\n".join(lines)


def format_profile(user) -> str:
    name = user.name or "—"
    if user.calorie_goal:
        goal = f"{user.calorie_goal} ккал / день"
    else:
        goal = "не задан"
    return (
        f"<b>Твой профиль</b>\n\n"
        f"Имя: {name}\n"
        f"Лимит калорий: {goal}"
    )
