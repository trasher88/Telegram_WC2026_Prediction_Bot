from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from repositories.users import ensure_user_registered, set_user_display_name
from states.profile import ProfileState
from utils import texts as T

router = Router()


def _normalize_display_name(value: str) -> str:
    return " ".join(value.strip().split())


def _validate_display_name(value: str) -> str | None:
    if not value:
        return "Имя не может быть пустым."

    if value.startswith("/"):
        return "Имя не должно начинаться с команды."

    if len(value) < 2:
        return "Имя слишком короткое. Минимум 2 символа."

    if len(value) > 30:
        return "Имя слишком длинное. Максимум 30 символов."

    return None


@router.message(Command("start"))
async def start(msg: types.Message, state: FSMContext):
    await state.clear()

    profile_complete = await ensure_user_registered(
        user_id=msg.from_user.id,
        username=msg.from_user.username,
        first_name=msg.from_user.first_name,
    )

    if not profile_complete:
        await state.update_data(rename_mode=False)
        await state.set_state(ProfileState.entering_name)
        await msg.answer(T.ASK_DISPLAY_NAME)
        return

    await msg.answer(T.WELCOME)


@router.message(Command("rename"))
async def rename(msg: types.Message, state: FSMContext):
    await ensure_user_registered(
        user_id=msg.from_user.id,
        username=msg.from_user.username,
        first_name=msg.from_user.first_name,
    )

    await state.clear()
    await state.update_data(rename_mode=True)
    await state.set_state(ProfileState.entering_name)
    await msg.answer(T.ASK_RENAME_DISPLAY_NAME)


@router.message(ProfileState.entering_name)
async def save_display_name(msg: types.Message, state: FSMContext):
    if not msg.text:
        await msg.answer(T.DISPLAY_NAME_NEED_TEXT)
        return

    display_name = _normalize_display_name(msg.text)
    error = _validate_display_name(display_name)

    if error:
        await msg.answer(T.display_name_invalid(error))
        return

    await ensure_user_registered(
        user_id=msg.from_user.id,
        username=msg.from_user.username,
        first_name=msg.from_user.first_name,
    )

    await set_user_display_name(
        user_id=msg.from_user.id,
        display_name=display_name,
    )

    data = await state.get_data()
    rename_mode = bool(data.get("rename_mode"))
    await state.clear()

    if rename_mode:
        await msg.answer(T.display_name_renamed(display_name))
        return

    await msg.answer(
        f"{T.display_name_saved(display_name)}\n\n"
        f"{T.WELCOME}"
    )


@router.message(Command("help"))
async def help_cmd(msg: types.Message):
    await msg.answer(T.HELP_TEXT)
