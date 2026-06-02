from aiogram import Router, types
from aiogram.filters import Command

from repositories.player_stats import (
    get_player_all_finished_predictions,
    get_player_open_predictions_count,
    get_player_recent_finished_predictions,
    get_player_total_predictions_count,
)
from services.scoring import calculate_points
from utils import texts as T
from utils.flags import COUNTRY_FLAGS
from utils.team_names import team_ru

router = Router()


@router.message(Command("form"))
async def player_form(msg: types.Message):
    rows = await get_player_recent_finished_predictions(
        user_id=msg.from_user.id,
        limit=10,
    )

    if not rows:
        await msg.answer(
            "📈 Форма игрока\n\n"
            "Пока нет завершённых матчей с твоими прогнозами."
        )
        return

    total_points = 0
    exact_count = 0

    text = "📈 Форма игрока\n"
    text += "Последние 10 завершённых прогнозов:\n\n"

    for row in rows:
        (
            match_id,
            home_team,
            away_team,
            start_time,
            home_score,
            away_score,
            home_pred,
            away_pred,
        ) = row

        points = calculate_points(
            home_pred,
            away_pred,
            home_score,
            away_score,
        )

        total_points += points

        if points == 2:
            icon = "✅"
            exact_count += 1
        elif points == 1:
            icon = "🟡"
        else:
            icon = "❌"

        home_flag = COUNTRY_FLAGS.get(home_team, "🏳")
        away_flag = COUNTRY_FLAGS.get(away_team, "🏳")

        text += (
            f"{icon} "
            f"{home_flag} {team_ru(home_team)} — "
            f"{away_flag} {team_ru(away_team)} "
            f"{home_score}:{away_score}\n"
            f"   Прогноз: {home_pred}:{away_pred} · "
            f"+{T.format_points(points)}\n\n"
        )

    max_points = len(rows) * 2
    average_points = total_points / len(rows)

    text += "──────────────\n"
    text += f"🎯 Точные счета: {exact_count}\n"
    text += f"🏆 Очки за форму: {total_points} из {max_points}\n"
    text += f"📊 Средний балл: {average_points:.2f}"

    await msg.answer(text)


@router.message(Command("my_stats"))
async def player_stats(msg: types.Message):
    rows = await get_player_all_finished_predictions(
        user_id=msg.from_user.id,
    )

    total_predictions = await get_player_total_predictions_count(
        user_id=msg.from_user.id,
    )

    open_predictions = await get_player_open_predictions_count(
        user_id=msg.from_user.id,
    )

    if not rows:
        await msg.answer(
            "📈 Статистика игрока\n\n"
            f"📌 Прогнозов всего: {total_predictions}\n"
            f"🕒 Ожидают результата: {open_predictions}\n\n"
            "Пока нет завершённых матчей с твоими прогнозами."
        )
        return

    total_points = 0
    exact_count = 0
    outcome_count = 0
    miss_count = 0

    for row in rows:
        (
            match_id,
            home_team,
            away_team,
            start_time,
            home_score,
            away_score,
            home_pred,
            away_pred,
        ) = row

        points = calculate_points(
            home_pred,
            away_pred,
            home_score,
            away_score,
        )

        total_points += points

        if points == 2:
            exact_count += 1
        elif points == 1:
            outcome_count += 1
        else:
            miss_count += 1

    finished_predictions = len(rows)
    max_points = finished_predictions * 2

    points_accuracy = (
        total_points / max_points * 100
        if max_points > 0
        else 0
    )

    result_accuracy = (
        (exact_count + outcome_count) / finished_predictions * 100
        if finished_predictions > 0
        else 0
    )

    exact_accuracy = (
        exact_count / finished_predictions * 100
        if finished_predictions > 0
        else 0
    )

    average_points = (
        total_points / finished_predictions
        if finished_predictions > 0
        else 0
    )

    current_streak_text = _build_current_streak_text(rows)

    text = "📈 Статистика игрока\n\n"

    text += f"🏆 Очки: {T.format_points(total_points)}\n"
    text += f"🎯 Точные счета: {exact_count}\n"
    text += f"🟡 Угаданные исходы: {outcome_count}\n"
    text += f"❌ Промахи: {miss_count}\n\n"

    text += f"📌 Прогнозов всего: {total_predictions}\n"
    text += f"✅ Завершённых прогнозов: {finished_predictions}\n"
    text += f"🕒 Ожидают результата: {open_predictions}\n\n"

    text += f"📊 Очковая эффективность: {points_accuracy:.1f}%\n"
    text += f"📈 Прогнозная точность: {result_accuracy:.1f}%\n"
    text += f"🎯 Точность счетов: {exact_accuracy:.1f}%\n"
    text += f"➗ Средний балл: {average_points:.2f}\n\n"

    text += current_streak_text

    await msg.answer(text)


def _build_current_streak_text(rows) -> str:
    """
    rows должны быть отсортированы от новых матчей к старым.
    Считаем текущую серию по последним завершённым прогнозам.
    """

    if not rows:
        return "🔥 Текущая серия: нет данных"

    first_row = rows[0]

    first_points = calculate_points(
        first_row[6],
        first_row[7],
        first_row[4],
        first_row[5],
    )

    if first_points > 0:
        streak_type = "points"
    else:
        streak_type = "miss"

    streak_count = 0
    exact_streak_count = 0

    for row in rows:
        points = calculate_points(
            row[6],
            row[7],
            row[4],
            row[5],
        )

        if streak_type == "points":
            if points > 0:
                streak_count += 1
            else:
                break
        else:
            if points == 0:
                streak_count += 1
            else:
                break

    for row in rows:
        points = calculate_points(
            row[6],
            row[7],
            row[4],
            row[5],
        )

        if points == 2:
            exact_streak_count += 1
        else:
            break

    if exact_streak_count > 0:
        return (
            f"🔥 Текущая серия: {streak_count} матч(а/ей) с очками\n"
            f"🎯 Серия точных счетов: {exact_streak_count}"
        )

    if streak_type == "points":
        return f"🔥 Текущая серия: {streak_count} матч(а/ей) с очками"

    return f"🧊 Текущая серия: {streak_count} матч(а/ей) без очков"