from aiogram.fsm.state import StatesGroup, State


class PredictState(StatesGroup):
    entering_score = State()