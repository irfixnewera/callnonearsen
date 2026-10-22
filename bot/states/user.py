from aiogram.fsm.state import State, StatesGroup


class OnboardingSG(StatesGroup):
    step = State()


class CorrectionSG(StatesGroup):
    waiting_text = State()


class ProfileSG(StatesGroup):
    waiting_name = State()
    waiting_goal = State()
