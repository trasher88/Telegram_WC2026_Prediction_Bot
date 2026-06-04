import asyncio
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from html import escape
from zoneinfo import ZoneInfo

import aiosqlite
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from config import APP_TIMEZONE
from db import DB_PATH
from repositories.leaderboard import get_leaderboard_data
from repositories.users import list_user_ids
from services.match_broadcasts import split_long_text
from services.scoring import calculate_points
from utils import texts as T
from utils.flags import COUNTRY_FLAGS
from utils.team_names import team_ru
from utils.user_names import user_display_name


DAILY_RESULTS = "daily_results_13"
GAME_DAY_START_HOUR = 13


MONTHS_RU = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}


def parse_match_time(start_time: str) -> datetime:
    dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt


def to_local_match_time(start_time: str) -> datetime:
    return parse_match_time(start_time).astimezone(ZoneInfo(APP_TIMEZONE))


def game_day_for_local_datetime(local_dt: datetime) -> date:
    if local_dt.hour < GAME_DAY_START_HOUR:
        return local_dt.date() - timedelta(days=1)

    return local_dt.date()


def current_game_day() -> date:
    now = datetime.now(ZoneInfo(APP_TIMEZONE))
    return game_day_for_local_datetime(now)


def previous_game_day() -> date:
    return current_game_day() - timedelta(days=1)


def format_game_day(value: date) -> str:
    return value.isoformat()


def format_game_day_title(value: date) -> str:
    month = MONTHS_RU.get(value.month, "")
    return f"{value.day} {month}".strip()


def exact_word(value: int) -> str:
    if value % 10 == 1 and value % 100 != 11:
        return "точный счёт"

    if value % 10 in [2, 3, 4] and value % 100 not in [12, 13, 14]:
        return "точных счёта"

    return "точных счетов"


def _match_result_line(match: dict) -> str:
    home_team = match["home_team"]
    away_team = match["away_team"]

    home_flag = COUNTRY_FLAGS.get(home_team, "🏳")
    away_flag = COUNTRY_FLAGS.get(away_team, "🏳")

    return (
        f"{home_flag} {escape(team_ru(home_team))} — "
        f"{away_flag} {escape(team_ru(away_team))} "
        f"{match['home_score']}:{match['away_score']}"
    )


async def _daily_results_already_sent(game_day: date) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        row = await (
            await db.execute(
                """
                SELECT 1
                FROM daily_notifications
                WHERE game_day = ?
                  AND notification_type = ?
                """,
                (format_game_day(game_day), DAILY_RESULTS),
            )
        ).fetchone()

    return row is not None


async def _mark_daily_results_sent(game_day: date) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO daily_notifications(game_day, notification_type)
            VALUES (?, ?)
            """,
            (format_game_day(game_day), DAILY_RESULTS),
        )

        await db.commit()


async def reset_daily_results_notification(game_day: date) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            DELETE FROM daily_notifications
            WHERE game_day = ?
              AND notification_type = ?
            """,
            (format_game_day(game_day), DAILY_RESULTS),
        )

        await db.commit()


async def get_matches_for_daily_results(game_day: date) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await (
            await db.execute(
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
                ORDER BY start_time
                """
            )
        ).fetchall()

    matches = []

    for (
        match_id,
        home_team,
        away_team,
        start_time,
        status,
        home_score,
        away_score,
    ) in rows:
        if not start_time:
            continue

        try:
            local_start = to_local_match_time(start_time)
        except ValueError:
            continue

        if game_day_for_local_datetime(local_start) != game_day:
            continue

        matches.append(
            {
                "id": match_id,
                "home_team": home_team,
                "away_team": away_team,
                "start_time": start_time,
                "local_start": local_start,
                "status": status,
                "home_score": home_score,
                "away_score": away_score,
            }
        )

    return matches


async def get_daily_player_results(match_ids: list[int]) -> list[dict]:
    if not match_ids:
        return []

    placeholders = ",".join("?" for _ in match_ids)

    async with aiosqlite.connect(DB_PATH) as db:
        rows = await (
            await db.execute(
                f"""
                SELECT
                    u.id,
                    u.display_name,
                    u.username,
                    u.first_name,
                    p.match_id,
                    p.home_score_pred,
                    p.away_score_pred,
                    m.home_score,
                    m.away_score
                FROM predictions p
                JOIN users u
                    ON u.id = p.user_id
                JOIN matches m
                    ON m.id = p.match_id
                WHERE p.match_id IN ({placeholders})
                """,
                match_ids,
            )
        ).fetchall()

    by_user = {}

    for (
        user_id,
        display_name,
        username,
        first_name,
        match_id,
        home_pred,
        away_pred,
        home_score,
        away_score,
    ) in rows:
        points = calculate_points(
            home_pred,
            away_pred,
            home_score,
            away_score,
        )

        if user_id not in by_user:
            by_user[user_id] = {
                "user_id": user_id,
                "display_name": display_name,
                "username": username,
                "first_name": first_name,
                "points": 0,
                "exact_scores": 0,
                "predictions": 0,
            }

        by_user[user_id]["points"] += points
        by_user[user_id]["predictions"] += 1

        if points == 2:
            by_user[user_id]["exact_scores"] += 1

    result = list(by_user.values())

    result.sort(
        key=lambda item: (
            -item["points"],
            -item["exact_scores"],
            user_display_name(
                item["user_id"],
                item["display_name"],
                item["username"],
                item["first_name"],
            ).lower(),
        )
    )

    return result


def _medal_for_position(position: int) -> str:
    if position == 1:
        return "🥇"

    if position == 2:
        return "🥈"

    if position == 3:
        return "🥉"

    return "•"


def _format_daily_points(players: list[dict]) -> str:
    if not players:
        return "Прогнозов на матчи этого игрового дня не было.\n"

    lines = []

    for index, player in enumerate(players, start=1):
        name = user_display_name(
            player["user_id"],
            player["display_name"],
            player["username"],
            player["first_name"],
            html=True,
        )

        prefix = _medal_for_position(index)

        lines.append(
            f"{prefix} {name} — {T.format_points(player['points'])}"
        )

    return "\n".join(lines) + "\n"


def _format_exact_scores(players: list[dict]) -> str:
    exact_players = [
        player
        for player in players
        if player["exact_scores"] > 0
    ]

    if not exact_players:
        return "Сегодня точных счетов не было.\n"

    lines = []

    for player in exact_players:
        name = user_display_name(
            player["user_id"],
            player["display_name"],
            player["username"],
            player["first_name"],
            html=True,
        )

        lines.append(
            f"• {name} — {player['exact_scores']}"
        )

    return "\n".join(lines) + "\n"


def _format_player_of_day(players: list[dict]) -> str:
    if not players:
        return "Игрок дня не определён.\n"

    best_points = players[0]["points"]
    best_exact = players[0]["exact_scores"]

    if best_points == 0:
        return "Игрок дня не определён: сегодня никто не набрал очков.\n"

    leaders = [
        player
        for player in players
        if player["points"] == best_points
        and player["exact_scores"] == best_exact
    ]

    if len(leaders) == 1:
        player = leaders[0]

        name = user_display_name(
            player["user_id"],
            player["display_name"],
            player["username"],
            player["first_name"],
            html=True,
        )

        return (
            f"{name} — "
            f"{T.format_points(player['points'])}, "
            f"{player['exact_scores']} {exact_word(player['exact_scores'])}\n"
        )

    names = [
        user_display_name(
            player["user_id"],
            player["display_name"],
            player["username"],
            player["first_name"],
            html=True,
        )
        for player in leaders
    ]

    return (
        f"{', '.join(names)} — "
        f"по {T.format_points(best_points)}, "
        f"{best_exact} {exact_word(best_exact)}\n"
    )


async def _format_current_leaderboard(limit: int = 5) -> str:
    top_players, _ranking = await get_leaderboard_data(limit=limit)

    if not top_players:
        return "Таблица пока пустая.\n"

    lines = []

    for index, row in enumerate(top_players, start=1):
        user_id = row[0]
        display_name = row[1]
        username = row[2]
        first_name = row[3]
        points = row[4] or 0

        name = user_display_name(
            user_id,
            display_name,
            username,
            first_name,
            html=True,
        )

        lines.append(f"{index}. {name} — {T.format_points(points)}")

    return "\n".join(lines) + "\n"


async def build_daily_results_summary(game_day: date) -> tuple[str | None, str | None]:
    matches = await get_matches_for_daily_results(game_day)

    if not matches:
        return None, f"Нет матчей для игрового дня {format_game_day(game_day)}"

    unfinished = [
        match
        for match in matches
        if match["status"] != "finished"
        or match["home_score"] is None
        or match["away_score"] is None
    ]

    if unfinished:
        return (
            None,
            (
                f"Не все матчи игрового дня {format_game_day(game_day)} завершены. "
                f"Всего матчей: {len(matches)}, незавершённых: {len(unfinished)}"
            ),
        )

    match_ids = [match["id"] for match in matches]
    players = await get_daily_player_results(match_ids)

    match_lines = "\n".join(
        _match_result_line(match)
        for match in matches
    )

    leaderboard_text = await _format_current_leaderboard(limit=5)

    text = (
        f"📊 <b>Итоги игрового дня — {format_game_day_title(game_day)}</b>\n\n"

        "⚽ <b>Матчи:</b>\n"
        f"{match_lines}\n\n"

        "🏆 <b>Очки за игровой день:</b>\n"
        f"{_format_daily_points(players)}\n"

        "🎯 <b>Точные счета:</b>\n"
        f"{_format_exact_scores(players)}\n"

        "🔥 <b>Игрок дня:</b>\n"
        f"{_format_player_of_day(players)}\n"

        "📌 <b>Текущая таблица:</b>\n"
        f"{leaderboard_text}"
    )

    return text, None


async def _send_html_message(bot: Bot, chat_id: int, text: str) -> bool:
    try:
        parts = split_long_text(text)

        for part in parts:
            await bot.send_message(
                chat_id=chat_id,
                text=part,
                parse_mode="HTML",
            )
            await asyncio.sleep(0.05)

        return True

    except (TelegramForbiddenError, TelegramBadRequest):
        return False

    except Exception as e:
        print(f"DAILY RESULTS ERROR chat_id={chat_id}: {e}")
        return False


async def send_daily_results_summary(
    bot: Bot,
    game_day: date | None = None,
    *,
    force: bool = False,
) -> None:
    game_day = game_day or previous_game_day()

    if not force and await _daily_results_already_sent(game_day):
        return

    text, error = await build_daily_results_summary(game_day)

    if error:
        print(f"Daily results skipped: {error}")
        return

    if not text:
        return

    user_ids = await list_user_ids()

    sent = 0
    failed = 0

    for user_id in user_ids:
        if await _send_html_message(bot, user_id, text):
            sent += 1
        else:
            failed += 1

    await _mark_daily_results_sent(game_day)

    print(
        f"Daily results sent for {format_game_day(game_day)}: "
        f"sent={sent}, failed={failed}"
    )