from aiogram import F, Router, types
from aiogram.filters import Command

from repositories.matches import get_group_matches_by_matchday, get_matches_by_stage
from handlers.keyboards import STAGE_TITLES, tournament_stage_keyboard
from utils import texts as T
from utils.formatter import format_match
from utils.flags import COUNTRY_FLAGS
from utils.team_names import team_ru

router = Router()

def format_finished_match_compact(home_team, away_team, home_score, away_score):
    home_flag = COUNTRY_FLAGS.get(home_team, "🏳")
    away_flag = COUNTRY_FLAGS.get(away_team, "🏳")

    return (
        f"{home_flag} {team_ru(home_team)} "
        f"{home_score}:{away_score} "
        f"{away_flag} {team_ru(away_team)}"
    )

@router.message(Command("matches"))
async def matches_menu(msg: types.Message):
    await msg.answer(
        T.CHOOSE_STAGE,
        reply_markup=tournament_stage_keyboard(
            group_prefix="group_",
            stage_prefix="stage_"
        )
    )


@router.callback_query(F.data.startswith("stage_"))
async def show_stage_matches(callback: types.CallbackQuery):
    stage = callback.data.replace("stage_", "")

    rows = await get_matches_by_stage(stage)

    if not rows:
        await callback.message.answer(T.NO_MATCHES_FOUND)
        await callback.answer()
        return

    stage_title = STAGE_TITLES.get(stage, stage)

    text = f"⚔️ {stage_title}\n\n"

    for r in rows:
        home = r[0]
        away = r[1]
        start_time = r[2]
        status = r[3]
        home_score = r[4]
        away_score = r[5]

        if status == "finished":
            text += format_finished_match_compact(
                home,
                away,
                home_score,
                away_score
            )
            text += "\n"
        else:
            text += format_match(
                home,
                away,
                start_time,
                status,
                home_score,
                away_score
            )
            text += "\n\n"

        text += "\n"

    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data.startswith("group_"))
async def show_group_round(callback: types.CallbackQuery):
    round_number = int(callback.data.split("_")[1])

    rows = await get_group_matches_by_matchday(round_number)

    if not rows:
        await callback.message.answer(T.NO_MATCHES_FOUND)
        await callback.answer()
        return

    text = (
        f"🌍 Групповой турнир: "
        f"Тур {round_number}\n\n"
    )

    for r in rows:
        home = r[0]
        away = r[1]
        start_time = r[2]
        status = r[3]
        home_score = r[4]
        away_score = r[5]

        if status == "finished":
            text += format_finished_match_compact(
                home,
                away,
                home_score,
                away_score
            )
            text += "\n"
        else:
            text += format_match(
                home,
                away,
                start_time,
                status,
                home_score,
                away_score
            )
            text += "\n"

        text += "\n"

    await callback.message.answer(text)
    await callback.answer()
