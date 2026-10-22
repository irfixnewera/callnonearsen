from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def result_kb(*, need_clarify: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if need_clarify:
        builder.row(
            InlineKeyboardButton(text="✏️ Уточнить", callback_data="result:correct"),
            InlineKeyboardButton(text="✅ Всё верно", callback_data="result:confirm"),
        )
    else:
        builder.row(
            InlineKeyboardButton(text="📝 Добавить в дневник", callback_data="diary:add"),
            InlineKeyboardButton(text="✏️ Исправить", callback_data="result:correct"),
        )
    builder.row(
        InlineKeyboardButton(text="🏠 Главная", callback_data="menu:main"),
    )
    return builder.as_markup()


def after_confirm_kb() -> InlineKeyboardMarkup:
    """После «Всё верно» — обычные действия с результатом."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📝 Добавить в дневник", callback_data="diary:add"),
        InlineKeyboardButton(text="✏️ Исправить", callback_data="result:correct"),
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Главная", callback_data="menu:main"),
    )
    return builder.as_markup()


def after_add_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 Дневник", callback_data="diary:today"),
        InlineKeyboardButton(text="🏠 Главная", callback_data="menu:main"),
    )
    return builder.as_markup()


def diary_period_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Сегодня", callback_data="diary:today"),
        InlineKeyboardButton(text="Вчера", callback_data="diary:yesterday"),
        InlineKeyboardButton(text="Неделя", callback_data="diary:week"),
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Главная", callback_data="menu:main"),
    )
    return builder.as_markup()


def diary_entry_kb(entry_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🗑 Удалить",
            callback_data=f"diary:delete:{entry_id}",
        ),
    )
    return builder.as_markup()


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 Дневник", callback_data="diary:today"),
        InlineKeyboardButton(text="👤 Профиль", callback_data="profile:show"),
    )
    builder.row(
        InlineKeyboardButton(text="❓ Помощь", callback_data="menu:help"),
    )
    return builder.as_markup()


def profile_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎯 Лимит калорий", callback_data="profile:set_goal"),
        InlineKeyboardButton(text="✏️ Имя", callback_data="profile:set_name"),
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Главная", callback_data="menu:main"),
    )
    return builder.as_markup()


def goal_presets_kb(*, include_skip: bool = False) -> InlineKeyboardMarkup:
    """Популярные лимиты для аудитории 40+ / контроль веса."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="1200", callback_data="goal:set:1200"),
        InlineKeyboardButton(text="1400", callback_data="goal:set:1400"),
        InlineKeyboardButton(text="1500", callback_data="goal:set:1500"),
    )
    builder.row(
        InlineKeyboardButton(text="1800", callback_data="goal:set:1800"),
        InlineKeyboardButton(text="2000", callback_data="goal:set:2000"),
    )
    builder.row(
        InlineKeyboardButton(text="Убрать лимит", callback_data="goal:set:0"),
    )
    if include_skip:
        builder.row(
            InlineKeyboardButton(text="Пропустить →", callback_data="onboarding:done"),
        )
    else:
        builder.row(
            InlineKeyboardButton(text="Отмена", callback_data="menu:cancel"),
        )
    return builder.as_markup()


def cancel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Отмена", callback_data="menu:cancel"),
    )
    return builder.as_markup()


def onboarding_kb(step: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if step < 3:
        builder.row(
            InlineKeyboardButton(text="Дальше →", callback_data=f"onboarding:{step + 1}"),
        )
    else:
        builder.row(
            InlineKeyboardButton(text="Начать 💛", callback_data="onboarding:done"),
        )
    return builder.as_markup()
