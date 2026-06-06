import asyncio
from html import escape

import aiosqlite
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from db import DB_PATH
from services.scoring import calculate_points
from utils.user_names import user_display_name

from utils.flags import COUNTRY_FLAGS
from utils.team_names import team_ru

try:
    from utils.team_names import team_ru
except ImportError:
    def team_ru(name):
        return name or "Неизвестная команда"


# Если у тебя есть функция флагов — потом можно подключить её здесь.
# Пока оставляем без флагов, чтобы код точно работал.
def team_display(team_name: str) -> str:
    return escape(team_ru(team_name))


def format_user_name(
    display_name,
    username,
    first_name,
    user_id
) -> str:
    return user_display_name(
        user_id,
        display_name=display_name,
        username=username,
        first_name=first_name,
        html=True,
    )


def points_text(points: int) -> str:
    if points == 1:
        return "1 очко"

    if points in [2, 3, 4]:
        return f"{points} очка"

    return f"{points} очков"


def split_long_text(
    text: str,
    limit: int = 3900
) -> list[str]:
    parts = []
    current = ""

    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > limit:
            parts.append(current)
            current = line
        else:
            current += line

    if current:
        parts.append(current)

    return parts


async def notification_already_sent(
    match_id: int,
    notification_type: str
) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT 1
            FROM match_notifications
            WHERE match_id = ?
            AND notification_type = ?
            """,
            (
                match_id,
                notification_type
            )
        )

        row = await cur.fetchone()

    return row is not None


async def mark_notification_sent(
    match_id: int,
    notification_type: str
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO match_notifications(
                match_id,
                notification_type
            )
            VALUES (?, ?)
            """,
            (
                match_id,
                notification_type
            )
        )

        await db.commit()


async def reset_notification(
    match_id: int,
    notification_type: str
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            DELETE FROM match_notifications
            WHERE match_id = ?
            AND notification_type = ?
            """,
            (
                match_id,
                notification_type
            )
        )

        await db.commit()


async def get_all_user_ids():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT id
            FROM users
            WHERE is_approved = 1
            """
        )

        rows = await cur.fetchall()

    return [row[0] for row in rows]


async def send_message_to_all_users(
    bot: Bot,
    text: str
):
    user_ids = await get_all_user_ids()

    # Для первого теста на основной bot.db можешь временно заменить строку выше на:
    # user_ids = [ТВОЙ_TELEGRAM_ID]

    sent = 0
    failed = 0

    for user_id in user_ids:
        try:
            for part in split_long_text(text):
                await bot.send_message(
                    chat_id=user_id,
                    text=part,
                    parse_mode="HTML"
                )

                await asyncio.sleep(0.05)

            sent += 1

        except TelegramForbiddenError:
            failed += 1

        except TelegramBadRequest:
            failed += 1

        except Exception as e:
            print(f"BROADCAST ERROR user_id={user_id}: {e}")
            failed += 1

    print(
        f"BROADCAST DONE: sent={sent}, failed={failed}"
    )


async def get_match(match_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT
                id,
                home_team,
                away_team,
                start_time,
                status,
                home_score,
                away_score
            FROM matches
            WHERE id = ?
            """,
            (match_id,)
        )

        return await cur.fetchone()


async def get_match_predictions(match_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT
                u.id,
                u.display_name,
                u.username,
                u.first_name,
                p.home_score_pred,
                p.away_score_pred
            FROM predictions p
            JOIN users u ON u.id = p.user_id
            WHERE p.match_id = ?
                AND u.is_approved = 1
            ORDER BY
                u.display_name COLLATE NOCASE,
                u.username COLLATE NOCASE,
                u.first_name COLLATE NOCASE,
                u.id
            """,
            (match_id,)
        )

        return await cur.fetchall()


async def build_lock_predictions_message(
    match_id: int
) -> str | None:
    match = await get_match(match_id)

    if not match:
        return None

    (
        _,
        home_team,
        away_team,
        start_time,
        status,
        home_score,
        away_score
    ) = match

    predictions = await get_match_predictions(match_id)

    home = team_display(home_team)
    away = team_display(away_team)
    home_flag = COUNTRY_FLAGS.get(home_team, "🏳")
    away_flag = COUNTRY_FLAGS.get(away_team, "🏳")

    text = (
        "🔒 <b>Прогнозы закрыты</b>\n\n"
        f"{home_flag} {team_ru(home_team)} — "
        f"{away_flag} {team_ru(away_team)}\n"
        "⏰ Матч скоро начнётся\n\n"
        "📊 <b>Прогнозы игроков:</b>\n"
    )

    if not predictions:
        text += (
            "Пока никто не сделал прогноз на этот матч.\n\n"
            "👥 Всего прогнозов: <b>0</b>"
        )

        return text

    for index, (
        user_id,
        display_name,
        username,
        first_name,
        home_pred,
        away_pred
    ) in enumerate(predictions, start=1):

        name = format_user_name(
            display_name,
            username,
            first_name,
            user_id
        )

        text += (
            f"{index}. {name} — "
            f"<b>{home_pred}:{away_pred}</b>\n"
        )

    text += (
        f"\n👥 Всего прогнозов: "
        f"<b>{len(predictions)}</b>"
    )

    return text


async def build_result_predictions_message(
    match_id: int
) -> str | None:
    match = await get_match(match_id)

    if not match:
        return None

    (
        _,
        home_team,
        away_team,
        start_time,
        status,
        home_score,
        away_score
    ) = match

    if status != "finished":
        return None

    if home_score is None or away_score is None:
        return None

    predictions = await get_match_predictions(match_id)

    home = team_display(home_team)
    away = team_display(away_team)
    home_flag = COUNTRY_FLAGS.get(home_team, "🏳")
    away_flag = COUNTRY_FLAGS.get(away_team, "🏳")

    text = (
        "🏁 <b>Матч завершён</b>\n"
        f"{home_flag} {team_ru(home_team)} — "
        f"{away_flag} {team_ru(away_team)} "
        f"{home_score}:{away_score}\n\n"
        "📊 <b>Результаты прогнозов:</b>\n"
    )

    if not predictions:
        text += "На этот матч не было прогнозов."
        return text

    results = []

    for (
        user_id,
        display_name,
        username,
        first_name,
        home_pred,
        away_pred
    ) in predictions:

        points = calculate_points(
            home_pred,
            away_pred,
            home_score,
            away_score
        )

        results.append(
            {
                "user_id": user_id,
                "display_name": display_name,
                "username": username,
                "first_name": first_name,
                "home_pred": home_pred,
                "away_pred": away_pred,
                "points": points,
            }
        )

    results.sort(
        key=lambda item: (
            -item["points"],
            item["display_name"] or item["username"] or item["first_name"] or str(item["user_id"])
        )
    )

    exact_players = []

    for index, item in enumerate(results, start=1):
        name = format_user_name(
            item["display_name"],
            item["username"],
            item["first_name"],
            item["user_id"]
        )

        points = item["points"]

        if points == 2:
            icon = "✅"
            exact_players.append(name)
        elif points == 1:
            icon = "🟡"
        else:
            icon = "❌"

        text += (
            f"{icon} {index}. {name} — "
            f"<b>{item['home_pred']}:{item['away_pred']}</b> "
            f"· +{points_text(points)}\n"
        )

    if exact_players:
        text += "\n🏆 <b>Точный счёт угадали:</b>\n"
        text += ", ".join(exact_players)
    else:
        text += "\n🏆 Точный счёт никто не угадал."

    return text


async def send_lock_predictions_broadcast(
    bot: Bot,
    match_id: int
):
    if await notification_already_sent(match_id, "lock"):
        return

    text = await build_lock_predictions_message(match_id)

    if not text:
        return

    await send_message_to_all_users(
        bot=bot,
        text=text
    )

    await mark_notification_sent(match_id, "lock")


async def send_result_predictions_broadcast(
    bot: Bot,
    match_id: int
):
    if await notification_already_sent(match_id, "result"):
        return

    text = await build_result_predictions_message(match_id)

    if not text:
        return

    await send_message_to_all_users(
        bot=bot,
        text=text
    )

    await mark_notification_sent(match_id, "result")