import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.repo import UserRepo
from bot.keyboards.inline import cancel_kb, goal_presets_kb, main_menu_kb, profile_kb
from bot.states.user import OnboardingSG, ProfileSG
from bot.texts import GOAL_CLEARED, GOAL_PROMPT, GOAL_SET, NAME_SET, ONBOARDING_3
from bot.utils.formatters import format_profile

logger = logging.getLogger(__name__)
router = Router(name="profile")


@router.callback_query(F.data == "profile:show")
async def show_profile(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    await callback.answer()
    repo = UserRepo(session)
    user = await repo.get_or_create(callback.from_user.id)
    text = format_profile(user)
    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=profile_kb(),
    )


@router.callback_query(F.data == "profile:set_name")
async def ask_name(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(ProfileSG.waiting_name)
    await callback.message.answer(
        "Как тебя называть?",
        reply_markup=cancel_kb(),
    )


@router.message(ProfileSG.waiting_name, F.text)
async def set_name(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    name = message.text.strip()[:64]
    repo = UserRepo(session)
    user = await repo.get_or_create(message.from_user.id)
    await repo.update_name(user, name)
    await state.clear()
    await message.answer(
        f"{NAME_SET}\n\nТеперь буду звать тебя {name} 💛",
        reply_markup=main_menu_kb(),
    )


@router.callback_query(F.data == "profile:set_goal")
async def ask_goal(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(ProfileSG.waiting_goal)
    await callback.message.answer(
        GOAL_PROMPT,
        reply_markup=goal_presets_kb(include_skip=False),
    )


@router.callback_query(F.data.startswith("goal:set:"))
async def set_goal_button(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    await callback.answer()
    value = int(callback.data.split(":")[2])
    repo = UserRepo(session)
    user = await repo.get_or_create(callback.from_user.id)

    if value <= 0:
        await repo.update_goal(user, None)
        text = GOAL_CLEARED
    else:
        await repo.update_goal(user, value)
        text = GOAL_SET.format(goal=value)

    # Если это онбординг — завершаем его
    current = await state.get_state()
    data = await state.get_data()
    if current == OnboardingSG.step.state or data.get("onboarding_step") == 3:
        await repo.mark_onboarding_done(user)
        await state.clear()
        await callback.message.edit_text(
            f"{text}\n\n{ONBOARDING_3}",
            reply_markup=main_menu_kb(),
        )
        return

    await state.clear()
    await callback.message.edit_text(text, reply_markup=main_menu_kb())


@router.message(ProfileSG.waiting_goal, F.text)
async def set_goal_text(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    text = message.text.strip().lower()
    repo = UserRepo(session)
    user = await repo.get_or_create(message.from_user.id)

    if text in {"убрать", "сбросить", "нет", "0"}:
        await repo.update_goal(user, None)
        await state.clear()
        await message.answer(GOAL_CLEARED, reply_markup=main_menu_kb())
        return

    try:
        goal = int(text.replace(" ", "").replace("ккал", ""))
        if goal < 800 or goal > 6000:
            await message.answer(
                "Укажи значение от 800 до 6000 ккал.",
                reply_markup=goal_presets_kb(),
            )
            return
    except ValueError:
        await message.answer(
            "Напиши число, например 1500 — или выбери кнопку.",
            reply_markup=goal_presets_kb(),
        )
        return

    await repo.update_goal(user, goal)
    await state.clear()
    await message.answer(
        GOAL_SET.format(goal=goal),
        reply_markup=main_menu_kb(),
    )
