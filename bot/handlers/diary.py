import json
import logging
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.repo import DiaryRepo, UserRepo
from bot.handlers.photo import ANALYSIS_KEY
from bot.keyboards.inline import after_add_kb, diary_entry_kb, diary_period_kb, main_menu_kb
from bot.services.gemini_vision import FoodAnalysis
from bot.texts import (
    ADDED_TO_DIARY,
    DIARY_EMPTY_TODAY,
    DIARY_EMPTY_WEEK,
    DIARY_EMPTY_YESTERDAY,
    ENTRY_DELETED,
)
from bot.utils.formatters import format_diary_day, format_goal_block

logger = logging.getLogger(__name__)
router = Router(name="diary")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


@router.callback_query(F.data == "diary:add")
async def add_to_diary(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    await callback.answer()
    data = await state.get_data()
    raw = data.get(ANALYSIS_KEY)
    if not raw:
        await callback.message.answer(
            "Сначала пришли фото еды 😊",
            reply_markup=main_menu_kb(),
        )
        return

    analysis = FoodAnalysis.model_validate(raw)
    user_repo = UserRepo(session)
    user = await user_repo.get_or_create(callback.from_user.id)

    diary_repo = DiaryRepo(session)
    await diary_repo.add_entry(
        user_id=user.id,
        items_json=json.dumps(
            [i.model_dump() for i in analysis.items], ensure_ascii=False
        ),
        calories=analysis.total.calories,
        protein=analysis.total.protein,
        fat=analysis.total.fat,
        carbs=analysis.total.carbs,
        comment=analysis.comment or None,
    )

    await state.update_data({ANALYSIS_KEY: None})
    await callback.message.edit_reply_markup(reply_markup=None)

    # Итог дня после добавления
    now = _now_utc()
    cal, _, _, _ = await diary_repo.get_day_totals(user.id, now)
    goal_line = format_goal_block(cal, user.calorie_goal)
    msg = ADDED_TO_DIARY
    if goal_line:
        msg = f"{ADDED_TO_DIARY}\n\n{goal_line}"

    await callback.message.answer(
        msg,
        parse_mode="HTML",
        reply_markup=after_add_kb(),
    )
    logger.info(
        "User %s added diary entry %s kcal",
        user.telegram_id,
        analysis.total.calories,
    )


@router.callback_query(F.data.in_({"diary:today", "diary:yesterday", "diary:week"}))
async def show_diary(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    await callback.answer()
    period = callback.data.split(":")[1]

    user_repo = UserRepo(session)
    user = await user_repo.get_or_create(callback.from_user.id)
    diary_repo = DiaryRepo(session)
    now = _now_utc()

    if period == "today":
        day = now
        title = "Сегодня"
        empty_text = DIARY_EMPTY_TODAY
        entries = await diary_repo.get_entries_for_day(user.id, day)
        totals = await diary_repo.get_day_totals(user.id, day)
    elif period == "yesterday":
        day = now - timedelta(days=1)
        title = "Вчера"
        empty_text = DIARY_EMPTY_YESTERDAY
        entries = await diary_repo.get_entries_for_day(user.id, day)
        totals = await diary_repo.get_day_totals(user.id, day)
    else:
        start = (now - timedelta(days=6)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end = now + timedelta(days=1)
        title = "За неделю"
        empty_text = DIARY_EMPTY_WEEK
        entries = await diary_repo.get_entries_for_period(user.id, start, end)
        cal = sum(e.calories for e in entries)
        prot = sum(e.protein for e in entries)
        fat = sum(e.fat for e in entries)
        carbs = sum(e.carbs for e in entries)
        totals = (cal, prot, fat, carbs)

    if not entries:
        text = f"<b>{title}</b>\n\n{empty_text}"
        if period == "today" and user.calorie_goal:
            text += f"\n\nЛимит на день: {user.calorie_goal} ккал"
    else:
        text = format_diary_day(entries, totals, title, user.calorie_goal)

    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=diary_period_kb(),
    )

    if period in {"today", "yesterday"} and entries:
        for entry in entries[:5]:
            time_str = entry.created_at.strftime("%H:%M")
            await callback.message.answer(
                f"{time_str} — {entry.calories} ккал",
                reply_markup=diary_entry_kb(entry.id),
            )


@router.callback_query(F.data.startswith("diary:delete:"))
async def delete_entry(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    await callback.answer()
    entry_id = int(callback.data.split(":")[2])

    user_repo = UserRepo(session)
    user = await user_repo.get_or_create(callback.from_user.id)
    diary_repo = DiaryRepo(session)

    deleted = await diary_repo.delete_entry(entry_id, user.id)
    if deleted:
        await callback.message.edit_text(ENTRY_DELETED)
    else:
        await callback.message.edit_text("Запись уже удалена или не найдена.")
