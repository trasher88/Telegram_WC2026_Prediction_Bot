from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import aiosqlite
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from api_client import APIClient
from config import APP_TIMEZONE, ENABLE_API_SYNC
from db import DB_PATH
from services.daily_notifications import (
    send_admin_daily_prediction_report,
    send_daily_matches_digest,
    send_missing_predictions_reminder,
)
from services.daily_results import send_daily_results_summary
from services.match_broadcasts import send_result_predictions_broadcast
from services.scoring import process_finished_match
from services.match_broadcasts import send_lock_predictions_broadcast

scheduler = AsyncIOScheduler()
api = APIClient()


def parse_start_time(start_time: str) -> datetime:
    dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt


def _to_int(value) -> int | None:
    """Safely convert API score values to int.

    Some APIs may return scores as strings. Empty values stay None.
    """
    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _score_pair(score: dict, key: str) -> tuple[int | None, int | None]:
    part = score.get(key) or {}

    return (
        _to_int(part.get("home")),
        _to_int(part.get("away")),
    )


def _remove_penalty_contamination_if_needed(
    home_score: int,
    away_score: int,
    pen_home: int,
    pen_away: int,
) -> tuple[int, int]:
    """
    Some APIs may already include penalty kicks in fullTime.

    Example of polluted data:
        fullTime 5:6, penalties 4:5

    Real score before penalties:
        5 - 4 = 1
        6 - 5 = 1

    So we restore 1:1 first and only then add +1 virtual goal
    to the shootout winner.
    """
    if home_score < pen_home or away_score < pen_away:
        return home_score, away_score

    possible_home_base = home_score - pen_home
    possible_away_base = away_score - pen_away

    # Before a penalty shootout the match score must be level.
    # If subtracting penalties gives a draw, the API score was polluted.
    if possible_home_base == possible_away_base:
        return possible_home_base, possible_away_base

    return home_score, away_score


def extract_tournament_score(score: dict) -> tuple[int | None, int | None]:
    """
    Возвращает счёт, который используется в турнире прогнозов.

    Главное правило для серии пенальти:
        пенальти НЕ прибавляются к счёту матча целиком.
        Победителю серии пенальти добавляется только +1 виртуальный гол.

    Примеры:
        fullTime 1:1, penalties 4:5 -> 1:2
        fullTime 0:0, penalties 5:4 -> 1:0
        fullTime 2:2, penalties 3:4 -> 2:3

    Защита от API, который уже прибавил пенальти к fullTime:
        fullTime 5:6, penalties 4:5 -> 1:2
        а не 5:6 и не 5:7
    """
    home_score, away_score = _score_pair(score, "fullTime")

    # Fallback на случай, если конкретный API не заполнил fullTime.
    # regularTime безопаснее, чем extraTime, потому что extraTime
    # в разных API может означать либо счёт после доп. времени,
    # либо только голы в доп. времени.
    if home_score is None or away_score is None:
        home_score, away_score = _score_pair(score, "regularTime")

    if home_score is None or away_score is None:
        return None, None

    pen_home, pen_away = _score_pair(score, "penalties")

    # Пенальти не было или API их не отдал — обычный счёт.
    if pen_home is None or pen_away is None:
        return home_score, away_score

    home_score, away_score = _remove_penalty_contamination_if_needed(
        home_score=home_score,
        away_score=away_score,
        pen_home=pen_home,
        pen_away=pen_away,
    )

    # Пенальти должны быть только после ничьей.
    # Если после восстановления базы счёт не равный,
    # не трогаем результат, чтобы не испортить обычный матч.
    if home_score != away_score:
        return home_score, away_score

    if pen_home > pen_away:
        return home_score + 1, away_score

    if pen_away > pen_home:
        return home_score, away_score + 1

    return home_score, away_score


def add_future_date_job(func, run_date: datetime, job_id: str, args: list):
    now = datetime.now(run_date.tzinfo or timezone.utc)

    if run_date <= now:
        return

    scheduler.add_job(
        func,
        "date",
        run_date=run_date,
        args=args,
        id=job_id,
        replace_existing=True
    )


def schedule_match_jobs(bot: Bot, match_id: int, start_time: str):
    """Schedule technical prediction lock for one match.

    User reminders are daily cron notifications now, not per-match jobs.
    """
    try:
        start = parse_start_time(start_time)

    except Exception as e:
        print(f"TIME PARSE ERROR for match {match_id}: {e}")
        return

    add_future_date_job(
        lock_predictions,
        start - timedelta(minutes=5),
        f"lock:{match_id}",
        [bot, match_id],
    )


def schedule_daily_notification_jobs(bot: Bot):
    tz = ZoneInfo(APP_TIMEZONE)

    if ENABLE_API_SYNC:
        scheduler.add_job(
            sync_matches,
            "cron",
            hour=12,
            minute=55,
            timezone=tz,
            args=[bot],
            id="sync_before_daily_results",
            replace_existing=True,
        )

    # 13:00 МСК — итоги прошедшего игрового дня
    scheduler.add_job(
        send_daily_results_summary,
        "cron",
        hour=13,
        minute=0,
        timezone=tz,
        args=[bot],
        id="daily_results_13_msk",
        replace_existing=True,
    )

    # 14:00 МСК — расписание текущего игрового дня
    scheduler.add_job(
        send_daily_matches_digest,
        "cron",
        hour=14,
        minute=0,
        timezone=tz,
        args=[bot],
        id="daily_digest_14_msk",
        replace_existing=True,
    )

    # 18:00 МСК — напоминание тем, кто ещё не поставил прогнозы
    scheduler.add_job(
        send_missing_predictions_reminder,
        "cron",
        hour=18,
        minute=0,
        timezone=tz,
        args=[bot],
        id="daily_missing_predictions_18_msk",
        replace_existing=True,
    )

    # 18:30 МСК — админский отчёт
    scheduler.add_job(
        send_admin_daily_prediction_report,
        "cron",
        hour=18,
        minute=30,
        timezone=tz,
        args=[bot],
        id="daily_admin_prediction_report_1830_msk",
        replace_existing=True,
    )


# ===============
# SYNC MATCHES
# ===============
async def sync_matches(bot):
    try:
        print("SYNC STARTED")
        data = await api.get_matches()

        if not data:
            print("SYNC ERROR: empty response")
            return

        if "matches" not in data:
            print("SYNC ERROR: no matches field")
            return

        finished_match_ids = []
        matches_to_schedule = []

        async with aiosqlite.connect(DB_PATH) as db:
            for m in data["matches"]:
                try:
                    match_id = m.get("id")

                    home_team = (
                        m.get("homeTeam", {})
                        .get("name", "Unknown")
                    )

                    away_team = (
                        m.get("awayTeam", {})
                        .get("name", "Unknown")
                    )

                    utc_date = m.get("utcDate")

                    status = (
                        m.get("status", "scheduled")
                        .lower()
                    )

                    stage = m.get("stage")
                    matchday = m.get("matchday")

                    home_score, away_score = extract_tournament_score(
                        m.get("score") or {}
                    )

                    status_for_db = status

                    if status == "finished" and (home_score is None or away_score is None):
                        print(
                            f"FINISHED MATCH WITHOUT SCORE: "
                            f"{match_id} {home_team} - {away_team}"
                        )
                        status_for_db = "timed"

                    if not match_id:
                        print("MATCH SKIPPED: no id")
                        continue

                    await db.execute(
                        """
                        INSERT INTO matches(
                            id,
                            home_team,
                            away_team,
                            start_time,
                            status,
                            stage,
                            matchday,
                            home_score,
                            away_score
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)

                        ON CONFLICT(id)
                        DO UPDATE SET
                            home_team = excluded.home_team,
                            away_team = excluded.away_team,
                            start_time = excluded.start_time,
                            status = excluded.status,
                            stage = excluded.stage,
                            matchday = excluded.matchday,
                            home_score = COALESCE(excluded.home_score, matches.home_score),
                            away_score = COALESCE(excluded.away_score, matches.away_score)
                        """,
                        (
                            match_id,
                            home_team,
                            away_team,
                            utc_date,
                            status_for_db,
                            stage,
                            matchday,
                            home_score,
                            away_score
                        )
                    )

                    if status_for_db == "finished":
                        finished_match_ids.append(match_id)

                    elif utc_date:
                        matches_to_schedule.append((match_id, utc_date))

                except Exception as e:
                    print(
                        f"MATCH ERROR "
                        f"{m.get('id')}: {e}"
                    )

            await db.commit()

        if scheduler.running:
            for match_id, utc_date in matches_to_schedule:
                schedule_match_jobs(bot, match_id, utc_date)

        for match_id in finished_match_ids:
            await process_finished_match(match_id)

            await send_result_predictions_broadcast(
                bot=bot,
                match_id=match_id
            )

        print("SYNC FINISHED")

    except Exception as e:
        print(f"SYNC CRITICAL ERROR: {e}")


# ===============
# LOCK PREDICTIONS
# ===============
async def lock_predictions(bot: Bot, match_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE matches
            SET locked = 1
            WHERE id = ?
            """,
            (match_id,),
        )

        await db.commit()

    await send_lock_predictions_broadcast(
        bot=bot,
        match_id=match_id,
    )

    print(f"Predictions locked and broadcast sent for match {match_id}")


# ===============
# SCHEDULER
# ===============
async def setup_scheduler(bot):
    scheduler.start()

    if ENABLE_API_SYNC:  # для теста БД
        scheduler.add_job(
            sync_matches,
            "interval",
            minutes=15,
            args=[bot],
            id="sync_matches",
            replace_existing=True
        )

    schedule_daily_notification_jobs(bot)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT
                id,
                start_time
            FROM matches
            WHERE status != 'finished'
            """
        ) as cur:
            rows = await cur.fetchall()

    for match_id, start_time in rows:
        schedule_match_jobs(bot, match_id, start_time)

    print("SCHEDULER READY")