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


def extract_tournament_score(score: dict) -> tuple[int | None, int | None]:
    """
    Возвращает счёт, который используется в турнире прогнозов.

    Обычный матч:
        берём score.fullTime.home / score.fullTime.away

    Матч с серией пенальти:
        берём fullTime-счёт и добавляем +1 гол победителю серии пенальти.

    Пример:
        fullTime 1:1, penalties 4:3 -> 2:1
        fullTime 1:1, penalties 2:4 -> 1:2
    """
    full_time = score.get("fullTime") or {}

    home_score = full_time.get("home")
    away_score = full_time.get("away")

    if home_score is None or away_score is None:
        return home_score, away_score

    penalties = score.get("penalties") or {}
    pen_home = penalties.get("home")
    pen_away = penalties.get("away")

    if pen_home is not None and pen_away is not None:
        if pen_home > pen_away:
            home_score += 1
        elif pen_away > pen_home:
            away_score += 1

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
                            home_score = excluded.home_score,
                            away_score = excluded.away_score
                        """,
                        (
                            match_id,
                            home_team,
                            away_team,
                            utc_date,
                            status,
                            stage,
                            matchday,
                            home_score,
                            away_score
                        )
                    )

                    if status == "finished":
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