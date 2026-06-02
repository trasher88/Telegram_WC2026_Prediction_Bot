from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from config import APP_TIMEZONE
from utils.flags import COUNTRY_FLAGS
from utils.team_names import team_ru


def _parse_utc_datetime(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt


def format_moscow_datetime(value: str) -> str:
    dt = _parse_utc_datetime(value)
    local_dt = dt.astimezone(ZoneInfo(APP_TIMEZONE))
    return local_dt.strftime("%Y/%m/%d %H:%M")


def format_match(
    home_team,
    away_team,
    start_time,
    status,
    home_score=None,
    away_score=None
):
    home_flag = COUNTRY_FLAGS.get(home_team, "🏳")
    away_flag = COUNTRY_FLAGS.get(away_team, "🏳")

    #dt = _parse_utc_datetime(start_time)
    #local_dt = dt.astimezone(ZoneInfo(APP_TIMEZONE))
    #formatted_time = local_dt.strftime("%Y/%m/%d %H:%M")
    formatted_time = format_moscow_datetime(start_time)

    home_team_ru = team_ru(home_team)
    away_team_ru = team_ru(away_team)

    if status == "finished":
        return (
            f"✅ {formatted_time}\n"
            f"{home_flag} {home_team_ru} "
            f"{home_score}:{away_score} "
            f"{away_flag} {away_team_ru}"
        )

    if status in ["in_play", "paused"]:
        return (
            f"🔴 LIVE\n"
            f"{home_flag} {home_team_ru} "
            f"{home_score}:{away_score} "
            f"{away_flag} {away_team_ru}"
        )

    return (
        f"🕒 {formatted_time}\n"
        f"{home_flag} {home_team_ru} "
        f"— "
        f"{away_flag} {away_team_ru}"
    )
