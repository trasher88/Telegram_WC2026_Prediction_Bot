from aiogram.fsm.state import State, StatesGroup


class ProfileState(StatesGroup):
    entering_name = State()
