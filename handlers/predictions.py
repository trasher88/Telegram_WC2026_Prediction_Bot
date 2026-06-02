import re

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from handlers.keyboards import prediction_score_keyboard, tournament_stage_keyboard
from repositories.matches import get_available_group_matches, get_available_stage_matches
from repositories.predictions import get_predicted_match_ids
from repositories.users import ensure_user_registered
from services.predictions import check_prediction_allowed, save_prediction_to_db
from states.predict import PredictState
from states.profile import ProfileState
from utils import texts as T
from utils.flags import COUNTRY_FLAGS
from utils.team_names import team_ru

router = Router()


@router.message(Command("predict"))
async def predict_menu(msg: types.Message, state: FSMContext):
    profile_complete = await ensure_user_registered(
        user_id=msg.from_user.id,
        username=msg.from_user.username,
        first_name=msg.from_user.first_name,
    )

    if not profile_complete:
        await state.clear()
        await state.update_data(rename_mode=False)
        await state.set_state(ProfileState.entering_name)
        await msg.answer(T.ASK_DISPLAY_NAME)
        return

    await msg.answer(
        T.CHOOSE_STAGE,
        reply_markup=tournament_stage_keyboard(
            group_prefix="predict_group_",
            stage_prefix="predict_stage_"
        )
    )


@router.callback_query(F.data.startswith("quick_predict_"))
async def quick_predict(callback: types.CallbackQuery, state: FSMContext):
    match_id = int(callback.data.split("_")[-1])

    allowed, error_text, match = await check_prediction_allowed(match_id)

    if not allowed:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        await callback.message.answer(error_text)
        await callback.answer()
        await state.clear()
        return

    await state.update_data(match_id=match_id)
    await state.set_state(PredictState.entering_score)

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await callback.message.answer(
        T.CHOOSE_SCORE,
        reply_markup=prediction_score_keyboard()
    )

    await callback.answer()


@router.callback_query(
    PredictState.entering_score,
    F.data.startswith("pred_score:")
)
async def prediction_score_button(
    callback: types.CallbackQuery,
    state: FSMContext
):
    payload = callback.data.split(":", 1)[1]

    if payload == "custom":
        await callback.answer()

        await callback.message.answer(
            "✍️ Введи свой прогноз\n"
            "Например: 2:1"
        )

        return

    try:
        home_pred, away_pred = map(
            int,
            payload.split(":")
        )
    except ValueError:
        await callback.answer(
            "Неверный счёт",
            show_alert=True
        )
        return

    data = await state.get_data()
    match_id = data.get("match_id")

    if not match_id:
        await callback.message.answer(
            "❌ Матч не выбран. Начни заново через /predict"
        )
        await state.clear()
        return

    allowed, error_text, match = await save_prediction_to_db(
        user_id=callback.from_user.id,
        match_id=match_id,
        home_pred=home_pred,
        away_pred=away_pred
    )

    if not allowed:
        await callback.message.answer(error_text)
        await state.clear()
        return

    home_team, away_team, start_time, status, locked = match

    try:
        await callback.message.delete()
    except Exception:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

    home_flag = COUNTRY_FLAGS.get(home_team, "🏳")
    away_flag = COUNTRY_FLAGS.get(away_team, "🏳")
    home_team_ru = team_ru(home_team)
    away_team_ru = team_ru(away_team)

    await callback.message.answer(
        f"✅ Прогноз сохранён\n"
        f"{home_team_ru} {home_flag} - {away_team_ru} {away_flag} {home_pred}:{away_pred}"
    )

    await callback.answer()
    await state.clear()


@router.message(PredictState.entering_score)
async def save_prediction(
    msg: types.Message,
    state: FSMContext
):
    if not msg.text:
        await msg.answer(T.NEED_TEXT_SCORE)
        return

    text = msg.text.strip()

    if not re.match(r"^\d+:\d+$", text):
        await msg.answer(T.INVALID_FORMAT)
        return

    home_pred, away_pred = map(
        int,
        text.split(":")
    )

    if home_pred > 20 or away_pred > 20:
        await msg.answer(T.UNREAL_SCORE)
        return

    data = await state.get_data()
    match_id = data.get("match_id")

    if not match_id:
        await msg.answer(T.GAME_NOT_CHOOSE)
        await state.clear()
        return

    allowed, error_text, match = await save_prediction_to_db(
        user_id=msg.from_user.id,
        match_id=match_id,
        home_pred=home_pred,
        away_pred=away_pred
    )

    if not allowed:
        await msg.answer(error_text)
        await state.clear()
        return

    home_team, away_team, start_time, status, locked = match

    home_flag = COUNTRY_FLAGS.get(home_team, "🏳")
    away_flag = COUNTRY_FLAGS.get(away_team, "🏳")
    home_team_ru = team_ru(home_team)
    away_team_ru = team_ru(away_team)

    await msg.answer(
        f"✅ Прогноз сохранён\n"
        f"{home_team_ru} {home_flag} - {away_team_ru} {away_flag} {home_pred}:{away_pred}"
    )

    await state.clear()


@router.callback_query(F.data.startswith("predict_group_"))
async def predict_group_matches(callback: types.CallbackQuery):
    round_number = int(callback.data.split("_")[2])
    user_id = callback.from_user.id

    rows = await get_available_group_matches(round_number)

    if not rows:
        await callback.message.answer(T.NO_MATCHES_AVAILABLE)
        await callback.answer()
        return

    predicted_matches = await get_predicted_match_ids(user_id)
    markup = _match_picker_keyboard(rows, predicted_matches)

    await callback.message.answer(
        T.CHOOSE_MATCH,
        reply_markup=markup
    )

    await callback.answer()


@router.callback_query(F.data.startswith("predict_stage_"))
async def predict_stage_matches(callback: types.CallbackQuery):
    stage = callback.data.replace("predict_stage_", "")
    user_id = callback.from_user.id

    rows = await get_available_stage_matches(stage)

    if not rows:
        await callback.message.answer(T.NO_MATCHES_AVAILABLE)
        await callback.answer()
        return

    predicted_matches = await get_predicted_match_ids(user_id)
    markup = _match_picker_keyboard(rows, predicted_matches)

    await callback.message.answer(
        T.CHOOSE_MATCH,
        reply_markup=markup
    )

    await callback.answer()


@router.callback_query(F.data.startswith("match_"))
async def choose_match(
    callback: types.CallbackQuery,
    state: FSMContext
):
    match_id = int(callback.data.split("_")[1])

    allowed, error_text, match = await check_prediction_allowed(match_id)

    if not allowed:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        await callback.message.answer(error_text)
        await callback.answer()
        await state.clear()
        return

    await state.update_data(match_id=match_id)
    await state.set_state(PredictState.entering_score)

    await callback.message.answer(
        T.CHOOSE_SCORE,
        reply_markup=prediction_score_keyboard()
    )

    await callback.answer()


@router.callback_query(F.data == "open_predict")
async def open_predict_callback(callback: types.CallbackQuery):
    await callback.message.answer(
        T.CHOOSE_STAGE,
        reply_markup=tournament_stage_keyboard(
            group_prefix="predict_group_",
            stage_prefix="predict_stage_"
        )
    )

    await callback.answer()


def _match_picker_keyboard(rows, predicted_matches: set[int]) -> InlineKeyboardMarkup:
    keyboard = []

    for r in rows:
        match_id = r[0]
        home_team = r[1]
        away_team = r[2]

        mark = "✅ " if match_id in predicted_matches else ""
        home_flag = COUNTRY_FLAGS.get(home_team, "🏳")
        away_flag = COUNTRY_FLAGS.get(away_team, "🏳")

        keyboard.append([
            InlineKeyboardButton(
                text=(
                    f"{mark}"
                    f"{home_flag} {team_ru(home_team)} — {away_flag} {team_ru(away_team)}"
                ),
                callback_data=f"match_{match_id}"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)
