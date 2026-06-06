import asyncio
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from html import escape
from zoneinfo import ZoneInfo

import aiosqlite
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import ADMIN_IDS, APP_TIMEZONE
from db import DB_PATH
from services.match_broadcasts import split_long_text
from utils.flags import COUNTRY_FLAGS
from utils.team_names import team_ru
from utils.user_names import user_display_name

DAILY_DIGEST = "digest_13"
DAILY_MISSING = "missing_18"
DAILY_ADMIN_REPORT = "admin_1830"
GAME_DAY_START_HOUR = 13


predict_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🎯 Сделать прогноз",
                callback_data="open_predict"
            )
        ]
    ]
)


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


def format_game_day(value: date) -> str:
    return value.isoformat()


def _match_display(home_team: str, away_team: str) -> str:
    home_flag = COUNTRY_FLAGS.get(home_team, "🏳️")
    away_flag = COUNTRY_FLAGS.get(away_team, "🏳️")

    return (
        f"{home_flag} {escape(team_ru(home_team))} — "
        f"{away_flag} {escape(team_ru(away_team))}"
    )


def _match_short_display(home_team: str, away_team: str) -> str:
    return f"{escape(team_ru(home_team))} — {escape(team_ru(away_team))}"


def format_match_line(match: dict, *, include_date: bool = True) -> str:
    local_dt = match["local_start"]
    time_format = "%d.%m %H:%M" if include_date else "%H:%M"

    return (
        f"🕒 {local_dt.strftime(time_format)}\n"
        f"{_match_display(match['home_team'], match['away_team'])}"
    )


async def _daily_notification_already_sent(game_day: date, notification_type: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        row = await (
            await db.execute(
                """
                SELECT 1
                FROM daily_notifications
                WHERE game_day = ?
                AND notification_type = ?
                """,
                (format_game_day(game_day), notification_type),
            )
        ).fetchone()

    return row is not None


async def _mark_daily_notification_sent(game_day: date, notification_type: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO daily_notifications(game_day, notification_type)
            VALUES (?, ?)
            """,
            (format_game_day(game_day), notification_type),
        )

        await db.commit()


async def reset_daily_notification(game_day: date, notification_type: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            DELETE FROM daily_notifications
            WHERE game_day = ?
            AND notification_type = ?
            """,
            (format_game_day(game_day), notification_type),
        )

        await db.commit()


async def get_matches_for_game_day(game_day: date, *, prediction_open_only: bool = False) -> list[dict]:
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
                    locked
                FROM matches
                WHERE status != 'finished'
                ORDER BY start_time
                """
            )
        ).fetchall()

    matches = []

    for match_id, home_team, away_team, start_time, status, locked in rows:
        if not start_time:
            continue

        try:
            local_start = to_local_match_time(start_time)
        except ValueError:
            continue

        if game_day_for_local_datetime(local_start) != game_day:
            continue

        if prediction_open_only and locked:
            continue

        matches.append(
            {
                "id": match_id,
                "home_team": home_team,
                "away_team": away_team,
                "start_time": start_time,
                "local_start": local_start,
                "status": status,
                "locked": locked,
            }
        )

    return matches


async def _get_users_prediction_status(match_ids: list[int]) -> list[dict]:
    if not match_ids:
        return []

    placeholders = ",".join("?" for _ in match_ids)

    async with aiosqlite.connect(DB_PATH) as db:
        users = await (
            await db.execute(
                """
                SELECT
                    id,
                    display_name,
                    username,
                    first_name
                FROM users
                WHERE is_approved = 1
                ORDER BY
                    display_name COLLATE NOCASE,
                    username COLLATE NOCASE,
                    first_name COLLATE NOCASE,
                    id
                """
            )
        ).fetchall()

        predictions = await (
            await db.execute(
                f"""
                SELECT user_id, match_id
                FROM predictions
                WHERE match_id IN ({placeholders})
                """,
                match_ids,
            )
        ).fetchall()

    predicted_by_user = defaultdict(set)

    for user_id, match_id in predictions:
        predicted_by_user[user_id].add(match_id)

    result = []

    for user_id, display_name, username, first_name in users:
        predicted_ids = predicted_by_user[user_id]
        missing_ids = [match_id for match_id in match_ids if match_id not in predicted_ids]

        result.append(
            {
                "user_id": user_id,
                "display_name": display_name,
                "username": username,
                "first_name": first_name,
                "predicted_ids": predicted_ids,
                "missing_ids": missing_ids,
            }
        )

    return result


async def _send_html_message(
    bot: Bot,
    chat_id: int,
    text: str,
    *,
    reply_markup=None,
) -> bool:
    try:
        parts = split_long_text(text)

        for index, part in enumerate(parts):
            await bot.send_message(
                chat_id=chat_id,
                text=part,
                parse_mode="HTML",
                reply_markup=reply_markup if index == len(parts) - 1 else None,
            )
            await asyncio.sleep(0.05)

        return True

    except (TelegramForbiddenError, TelegramBadRequest):
        return False

    except Exception as e:
        print(f"DAILY NOTIFICATION ERROR chat_id={chat_id}: {e}")
        return False


async def send_daily_matches_digest(
    bot: Bot,
    game_day: date | None = None,
    *,
    force: bool = False,
) -> None:
    game_day = game_day or current_game_day()

    if not force and await _daily_notification_already_sent(game_day, DAILY_DIGEST):
        return

    matches = await get_matches_for_game_day(game_day)

    if not matches:
        print(f"Ежедневный дайджест пропущен: совпадений не найдено {format_game_day(game_day)}")
        return

    async with aiosqlite.connect(DB_PATH) as db:
        users = await (
            await db.execute(
                """
                SELECT id
                FROM users
                WHERE is_approved = 1
                """
            )
        ).fetchall()

    lines = "\n".join(format_match_line(match) for match in matches)

    text = (
        "⚽ Матчи игрового дня\n\n"
        f"{lines}\n\n"
        "Не забудь поставить прогнозы!"
    )

    sent = 0
    failed = 0

    for (user_id,) in users:
        if await _send_html_message(bot, user_id, text, reply_markup=predict_keyboard):
            sent += 1
        else:
            failed += 1

    await _mark_daily_notification_sent(game_day, DAILY_DIGEST)
    print(
        f"Daily digest sent for {format_game_day(game_day)}: "
        f"sent={sent}, failed={failed}"
    )


async def send_missing_predictions_reminder(
    bot: Bot,
    game_day: date | None = None,
    *,
    force: bool = False,
) -> None:
    game_day = game_day or current_game_day()

    if not force and await _daily_notification_already_sent(game_day, DAILY_MISSING):
        return

    matches = await get_matches_for_game_day(game_day, prediction_open_only=True)

    if not matches:
        print(f"Напоминание пропущено: нет открытых матчей для {format_game_day(game_day)}")
        return

    match_ids = [match["id"] for match in matches]
    matches_by_id = {match["id"]: match for match in matches}
    statuses = await _get_users_prediction_status(match_ids)

    sent = 0
    failed = 0

    for user in statuses:
        missing_ids = user["missing_ids"]

        if not missing_ids:
            continue

        missing_lines = "\n".join(
            format_match_line(matches_by_id[match_id])
            for match_id in missing_ids
        )

        text = (
            "⏰ <b>Напоминание</b>\n\n"
            f"У тебя ещё нет прогнозов на {len(missing_ids)} "
            f"матч(а):\n"
            f"{missing_lines}\n\n"
            "Поставь прогноз до закрытия приёма."
        )

        if await _send_html_message(
            bot,
            user["user_id"],
            text,
            reply_markup=predict_keyboard,
        ):
            sent += 1
        else:
            failed += 1

    await _mark_daily_notification_sent(game_day, DAILY_MISSING)
    print(
        f"Missing reminders sent for {format_game_day(game_day)}: "
        f"sent={sent}, failed={failed}"
    )


async def send_admin_daily_prediction_report(
    bot: Bot,
    game_day: date | None = None,
    *,
    force: bool = False,
) -> None:
    game_day = game_day or current_game_day()

    if not force and await _daily_notification_already_sent(game_day, DAILY_ADMIN_REPORT):
        return

    matches = await get_matches_for_game_day(game_day)

    if not matches:
        print(f"Ежедневный отчет администратора пропущен: совпадений не найдено {format_game_day(game_day)}")
        return

    match_ids = [match["id"] for match in matches]
    matches_by_id = {match["id"]: match for match in matches}
    statuses = await _get_users_prediction_status(match_ids)

    complete = []
    partial = []
    empty = []

    for user in statuses:
        if not user["missing_ids"]:
            complete.append(user)
        elif not user["predicted_ids"]:
            empty.append(user)
        else:
            partial.append(user)

    match_lines = "\n".join(
        f"{index}. {format_match_line(match)}"
        for index, match in enumerate(matches, start=1)
    )

    text = (
        f"📊 <b>Отчёт по прогнозам на игровой день {format_game_day(game_day)}</b>\n\n"
        "<b>Матчи:</b>\n"
        f"{match_lines}\n\n"
        f"👥 Всего игроков: <b>{len(statuses)}</b>\n"
        f"✅ Поставили все прогнозы: <b>{len(complete)}</b>\n"
        f"⚠️ Частично поставили: <b>{len(partial)}</b>\n"
        f"❌ Не поставили ничего: <b>{len(empty)}</b>\n\n"
    )

    if complete:
        text += "✅ <b>Поставили все:</b>\n"
        for user in complete:
            text += (
                "• "
                f"{user_display_name(user['user_id'], user['display_name'], user['username'], user['first_name'], html=True, include_username=True)}\n"
            )
        text += "\n"

    if partial:
        text += "⚠️ <b>Не хватает прогнозов:</b>\n"

        for user in partial:
            user_name = user_display_name(
                user["user_id"],
                user["display_name"],
                user["username"],
                user["first_name"],
                html=True,
                include_username=True,
            )

            text += f"• {user_name} — нет:\n"

            for match_id in user["missing_ids"]:
                match_title = _match_short_display(
                    matches_by_id[match_id]["home_team"],
                    matches_by_id[match_id]["away_team"],
                )
                text += f"   - {match_title}\n"

            text += "\n"

    if empty:
        text += "❌ <b>Не поставили ничего:</b>\n"
        for user in empty:
            text += (
                "• "
                f"{user_display_name(user['user_id'], user['display_name'], user['username'], user['first_name'], html=True, include_username=True)}\n"
            )

    for admin_id in ADMIN_IDS:
        await _send_html_message(bot, admin_id, text)

    await _mark_daily_notification_sent(game_day, DAILY_ADMIN_REPORT)
    print(f"Admin daily report sent for {format_game_day(game_day)}")
