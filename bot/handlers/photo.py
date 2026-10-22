import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.repo import DiaryRepo, UserRepo
from bot.keyboards.inline import after_confirm_kb, result_kb
from bot.services.gemini_vision import FoodAnalysis, GeminiVisionService
from bot.texts import (
    ANALYZING_STEPS,
    NOT_FOOD,
    RECOGNITION_FAILED,
    RESULT_FOOTER,
)
from bot.utils.formatters import format_food_result, needs_clarification

logger = logging.getLogger(__name__)
router = Router(name="photo")

ANALYSIS_KEY = "last_analysis"


async def _animate_analysis(msg: Message, steps: list[str]) -> None:
    for step in steps:
        try:
            await msg.edit_text(step)
            await asyncio.sleep(0.9)
        except Exception:
            pass


async def _today_eaten_and_goal(
    session: AsyncSession, telegram_id: int
) -> tuple[int, int | None]:
    user_repo = UserRepo(session)
    user = await user_repo.get_or_create(telegram_id)
    diary_repo = DiaryRepo(session)
    now = datetime.now(timezone.utc)
    cal, _, _, _ = await diary_repo.get_day_totals(user.id, now)
    return cal, user.calorie_goal


@router.message(F.photo)
async def handle_photo(
    message: Message,
    bot: Bot,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    await state.clear()

    photo = message.photo[-1]
    status_msg = await message.answer(ANALYZING_STEPS[0])
    anim_task = asyncio.create_task(_animate_analysis(status_msg, ANALYZING_STEPS))

    try:
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)
        image_data = file_bytes.read()

        service = GeminiVisionService()
        analysis: FoodAnalysis = await service.analyze_photo(image_data)

        anim_task.cancel()
        try:
            await anim_task
        except asyncio.CancelledError:
            pass

        if not analysis.is_food:
            await status_msg.edit_text(NOT_FOOD)
            return

        eaten, goal = await _today_eaten_and_goal(session, message.from_user.id)
        unsure = needs_clarification(analysis)

        await state.update_data({ANALYSIS_KEY: analysis.model_dump()})

        text = format_food_result(
            analysis,
            eaten_today=eaten,
            goal=goal,
            show_clarify_hint=unsure,
        )
        await status_msg.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=result_kb(need_clarify=unsure),
        )
        logger.info(
            "User %s analyzed photo: %s kcal (clarify=%s)",
            message.from_user.id,
            analysis.total.calories,
            unsure,
        )

    except Exception as exc:
        anim_task.cancel()
        try:
            await anim_task
        except asyncio.CancelledError:
            pass
        logger.exception(
            "Photo analysis failed for user %s: %s", message.from_user.id, exc
        )
        await status_msg.edit_text(RECOGNITION_FAILED)


@router.callback_query(F.data == "result:confirm")
async def confirm_uncertain_result(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Пользователь нажал «Всё верно» при сомнении ИИ — убираем хинт, даём обычные кнопки."""
    await callback.answer()
    data = await state.get_data()
    raw = data.get(ANALYSIS_KEY)
    if not raw:
        await callback.message.answer("Сначала пришли фото еды 😊")
        return

    analysis = FoodAnalysis.model_validate(raw)
    eaten, goal = await _today_eaten_and_goal(session, callback.from_user.id)
    text = format_food_result(
        analysis,
        eaten_today=eaten,
        goal=goal,
        show_clarify_hint=False,
    )
    # Добавим приятный футер, если его не было
    if RESULT_FOOTER not in text:
        text = text + "\n\n" + RESULT_FOOTER

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=after_confirm_kb(),
    )
