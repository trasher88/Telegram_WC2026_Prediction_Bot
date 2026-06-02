from aiogram import Router, types
from aiogram.filters import Command

from repositories.leaderboard import get_leaderboard_data
from utils import texts as T
from utils.user_names import user_display_name

router = Router()


@router.message(Command("leaderboard"))
async def leaderboard(msg: types.Message):
    user_id = msg.from_user.id

    top_players, ranking = await get_leaderboard_data(limit=10)

    user_position = None
    user_points = 0

    for idx, row in enumerate(ranking, start=1):
        if row[0] == user_id:
            user_position = idx
            user_points = row[1]
            break

    text = T.LEADERBOARD_TITLE

    medals = {
        1: "🥇",
        2: "🥈",
        3: "🥉"
    }

    for idx, row in enumerate(top_players, start=1):
        uid = row[0]
        display_name = row[1]
        username = row[2]
        first_name = row[3]
        points = row[4] or 0
        predictions = row[5] or 0
        exact_scores = row[6] or 0

        medal = medals.get(idx, f"{idx}.")
        safe_name = user_display_name(
            uid,
            display_name=display_name,
            username=username,
            first_name=first_name,
            html=True,
        )

        text += (
            f"{medal} {safe_name} - "
            f"<b>{T.format_points(points)}</b> "
            f"({exact_scores}) "
            f"(прогнозов: {predictions})\n"
        )

    if user_position:
        text += (
            "\n"
            "______________\n"
            f"{T.YOUR_POSITION}\n"
            f"#{user_position} — "
            f"<b>{T.format_points(user_points)}</b>"
        )

    await msg.answer(
        text,
        parse_mode="HTML"
    )
