import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.repo import UserRepo
from bot.keyboards.inline import goal_presets_kb, main_menu_kb, onboarding_kb
from bot.states.user import OnboardingSG
from bot.texts import (
    HELP,
    ONBOARDING_1,
    ONBOARDING_2,
    ONBOARDING_3,
    ONBOARDING_GOAL,
)

logger = logging.getLogger(__name__)
router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    repo = UserRepo(session)
    user = await repo.get_or_create(
        telegram_id=message.from_user.id,
        name=message.from_user.first_name,
    )

    if not user.onboarding_done:
        await state.set_state(OnboardingSG.step)
        await state.update_data(onboarding_step=1)
        await message.answer(
            ONBOARDING_1,
            reply_markup=onboarding_kb(1),
        )
        return

    name = user.name or "друг"
    extra = ""
    if user.calorie_goal:
        extra = f"\nЛимит на сегодня: {user.calorie_goal} ккал."
    await message.answer(
        f"Снова привет, {name} 💛\n\n"
        f"Просто пришли фото еды — я всё посчитаю.{extra}",
        reply_markup=main_menu_kb(),
    )


@router.callback_query(F.data.startswith("onboarding:"))
async def onboarding_step(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    await callback.answer()
    data = callback.data.split(":")[1]

    if data == "done":
        repo = UserRepo(session)
        user = await repo.get_or_create(callback.from_user.id)
        await repo.mark_onboarding_done(user)
        await state.clear()
        await callback.message.edit_text(
            ONBOARDING_3,
            reply_markup=main_menu_kb(),
        )
        return

    step = int(data)
    if step == 2:
        await state.update_data(onboarding_step=2)
        await callback.message.edit_text(
            ONBOARDING_2,
            reply_markup=onboarding_kb(2),
        )
    elif step == 3:
        # Шаг про лимит калорий
        await state.update_data(onboarding_step=3)
        await callback.message.edit_text(
            ONBOARDING_GOAL,
            reply_markup=goal_presets_kb(include_skip=True),
        )
    else:
        await callback.message.edit_text(
            ONBOARDING_1,
            reply_markup=onboarding_kb(1),
        )


@router.message(Command("help"))
@router.callback_query(F.data == "menu:help")
async def cmd_help(event: Message | CallbackQuery) -> None:
    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.answer(HELP, reply_markup=main_menu_kb())
    else:
        await event.answer(HELP, reply_markup=main_menu_kb())


@router.callback_query(F.data == "menu:main")
async def menu_main(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await callback.message.answer(
        "Главное меню.\n\nПросто пришли фото еды 🍽",
        reply_markup=main_menu_kb(),
    )


@router.callback_query(F.data == "menu:cancel")
async def menu_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    from bot.texts import CANCELLED

    await callback.message.edit_text(CANCELLED, reply_markup=main_menu_kb())
