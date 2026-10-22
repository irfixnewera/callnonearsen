import logging
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.repo import DiaryRepo, UserRepo
from bot.handlers.photo import ANALYSIS_KEY
from bot.keyboards.inline import cancel_kb, result_kb
from bot.services.gemini_vision import FoodAnalysis, GeminiVisionService
from bot.states.user import CorrectionSG
from bot.texts import (
    CORRECTION_APPLIED,
    CORRECTION_FAILED,
    CORRECTION_PROMPT,
)
from bot.utils.formatters import format_food_result, needs_clarification

logger = logging.getLogger(__name__)
router = Router(name="correction")


@router.callback_query(F.data == "result:correct")
async def start_correction(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    if not data.get(ANALYSIS_KEY):
        await callback.message.answer("Сначала пришли фото еды 😊")
        return

    await state.set_state(CorrectionSG.waiting_text)
    await callback.message.answer(
        CORRECTION_PROMPT,
        reply_markup=cancel_kb(),
    )


@router.message(CorrectionSG.waiting_text, F.text)
async def apply_text_correction(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    raw = data.get(ANALYSIS_KEY)
    if not raw:
        await state.clear()
        await message.answer("Сначала пришли фото еды 😊")
        return

    current = FoodAnalysis.model_validate(raw)
    status = await message.answer("Исправляю...")

    try:
        service = GeminiVisionService()
        updated = await service.apply_correction(current, message.text.strip())
        await state.update_data({ANALYSIS_KEY: updated.model_dump()})
        await state.set_state(None)

        user_repo = UserRepo(session)
        user = await user_repo.get_or_create(message.from_user.id)
        diary_repo = DiaryRepo(session)
        cal, _, _, _ = await diary_repo.get_day_totals(
            user.id, datetime.now(timezone.utc)
        )

        # После ручной правки считаем, что пользователь подтвердил — без хинта
        text = format_food_result(
            updated,
            eaten_today=cal,
            goal=user.calorie_goal,
            show_clarify_hint=False,
        )
        await status.edit_text(
            f"{CORRECTION_APPLIED}\n\n{text}",
            parse_mode="HTML",
            reply_markup=result_kb(need_clarify=False),
        )
    except Exception as exc:
        logger.exception("Correction failed: %s", exc)
        await status.edit_text(CORRECTION_FAILED, reply_markup=cancel_kb())


@router.message(CorrectionSG.waiting_text, F.voice)
async def apply_voice_correction(
    message: Message,
    state: FSMContext,
) -> None:
    await message.answer(
        "Пока принимаю только текст 💛\n\n"
        "Напиши, например: «грудки было 200 г»",
        reply_markup=cancel_kb(),
    )
