from html import escape

from aiogram import F, Router, types
from aiogram.filters import Command

from repositories.predictions import get_user_predictions
from handlers.keyboards import STAGE_TITLES, tournament_stage_keyboard
from services.predictions import calculate_prediction_result
from utils.flags import COUNTRY_FLAGS
from utils.team_names import team_ru

router = Router()


@router.message(Command("my_predictions"))
async def my_predictions_menu(msg: types.Message):
    await msg.answer(
        "📋 Выбери стадию, чтобы посмотреть свои прогнозы:",
        reply_markup=tournament_stage_keyboard(
            group_prefix="mypred_group_",
            stage_prefix="mypred_stage_"
        )
    )


async def build_my_predictions_text(
    user_id: int,
    title: str,
    stage: str | None = None,
    matchday: int | None = None
) -> str:
    rows = await get_user_predictions(
        user_id=user_id,
        stage=stage,
        matchday=matchday
    )

    if not rows:
        return (
            f"📋 <b>{escape(title)}</b>\n\n"
            "У тебя пока нет прогнозов в этом разделе."
        )

    text = f"📋 <b>{escape(title)}</b>\n\n"
    total_points = 0

    for row in rows:
        (
            home_team,
            away_team,
            home_score,
            away_score,
            pred_home,
            pred_away,
            status,
            start_time
        ) = row

        home_flag = COUNTRY_FLAGS.get(home_team, "🏳️")
        away_flag = COUNTRY_FLAGS.get(away_team, "🏳️")

        result_text, points = calculate_prediction_result(
            pred_home,
            pred_away,
            home_score,
            away_score,
            status
        )

        total_points += points

        if (
            home_score is not None
            and away_score is not None
            and status == "finished"
        ):
            score_line = f"{home_score}:{away_score}"
        else:
            score_line = "—"

        text += (
            f"{result_text}\n"
            f"{home_flag} {escape(team_ru(home_team))} "
            f"{score_line} "
            f"{escape(team_ru(away_team))} {away_flag}\n"
            f"🎯 Прогноз: <b>{pred_home}:{pred_away}</b>\n"
            f"━━━━━━━━━━━━━━\n\n"
        )

    text += (
        f"🏆 Очков в этом разделе: "
        f"<b>{total_points}</b>"
    )

    return text


@router.callback_query(F.data.startswith("mypred_group_"))
async def my_predictions_group(callback: types.CallbackQuery):
    round_number = int(callback.data.split("_")[2])

    text = await build_my_predictions_text(
        user_id=callback.from_user.id,
        title=f"Мои прогнозы — тур {round_number}",
        matchday=round_number
    )

    await _send_long_html(callback, text)
    await callback.answer()


@router.callback_query(F.data.startswith("mypred_stage_"))
async def my_predictions_stage(callback: types.CallbackQuery):
    stage = callback.data.replace("mypred_stage_", "")
    title = STAGE_TITLES.get(stage, stage)

    text = await build_my_predictions_text(
        user_id=callback.from_user.id,
        title=f"Мои прогнозы — {title}",
        stage=stage
    )

    await _send_long_html(callback, text)
    await callback.answer()


async def _send_long_html(callback: types.CallbackQuery, text: str):
    limit = 3500

    for i in range(0, len(text), limit):
        await callback.message.answer(
            text[i:i + limit],
            parse_mode="HTML"
        )
