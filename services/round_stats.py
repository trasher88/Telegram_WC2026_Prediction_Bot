from collections import Counter
from html import escape

import aiosqlite
from aiogram import Bot

from db import DB_PATH
from services.match_broadcasts import send_message_to_all_users
from services.scoring import calculate_points
from utils.flags import COUNTRY_FLAGS
from utils.team_names import team_ru
from utils.user_names import user_display_name


STAGE_ALIASES = {
    "1_16": (["LAST_32"], "1/16 финала"),
    "1/16": (["LAST_32"], "1/16 финала"),
    "last32": (["LAST_32"], "1/16 финала"),
    "last_32": (["LAST_32"], "1/16 финала"),
    "last-32": (["LAST_32"], "1/16 финала"),

    "1_8": (["LAST_16"], "1/8 финала"),
    "1/8": (["LAST_16"], "1/8 финала"),
    "last16": (["LAST_16"], "1/8 финала"),
    "last_16": (["LAST_16"], "1/8 финала"),
    "last-16": (["LAST_16"], "1/8 финала"),

    "1_4": (["QUARTER_FINALS"], "1/4 финала"),
    "1/4": (["QUARTER_FINALS"], "1/4 финала"),
    "quarter": (["QUARTER_FINALS"], "1/4 финала"),
    "quarters": (["QUARTER_FINALS"], "1/4 финала"),
    "quarter_finals": (["QUARTER_FINALS"], "1/4 финала"),

    "1_2": (["SEMI_FINALS"], "1/2 финала"),
    "1/2": (["SEMI_FINALS"], "1/2 финала"),
    "semi": (["SEMI_FINALS"], "1/2 финала"),
    "semis": (["SEMI_FINALS"], "1/2 финала"),
    "semi_finals": (["SEMI_FINALS"], "1/2 финала"),

    "third": (["THIRD_PLACE", "THIRD_PLACE_PLAYOFF"], "матча за 3-е место"),
    "3": (["THIRD_PLACE", "THIRD_PLACE_PLAYOFF"], "матча за 3-е место"),
    "third_place": (["THIRD_PLACE", "THIRD_PLACE_PLAYOFF"], "матча за 3-е место"),
    "third-place": (["THIRD_PLACE", "THIRD_PLACE_PLAYOFF"], "матча за 3-е место"),

    "final": (["FINAL"], "финала"),
    "finals": (["FINAL"], "финала"),
}


def outcome(home: int, away: int) -> int:
    if home > away:
        return 1

    if home < away:
        return -1

    return 0


def points_text(points: int) -> str:
    if points == 1:
        return "1 очко"

    if points in (2, 3, 4):
        return f"{points} очка"

    return f"{points} очков"


def percent_text(value: float) -> str:
    return f"{value:.1f}%"


def round_title(matchday: int) -> str:
    if matchday == 1:
        return "1-го тура группового этапа"

    if matchday == 2:
        return "2-го тура группового этапа"

    if matchday == 3:
        return "3-го тура группового этапа"

    return f"{matchday}-го тура группового этапа"


def normalize_stage_arg(raw_stage: str) -> tuple[list[str], str]:
    key = raw_stage.strip().lower()

    if key in STAGE_ALIASES:
        return STAGE_ALIASES[key]

    stage = raw_stage.strip().upper()
    return [stage], stage


def medal(index: int) -> str:
    if index == 1:
        return "🥇"

    if index == 2:
        return "🥈"

    if index == 3:
        return "🥉"

    return f"{index}."


def format_player_name(row: dict) -> str:
    return user_display_name(
        row["user_id"],
        display_name=row["display_name"],
        username=row["username"],
        first_name=row["first_name"],
        html=True,
    )


def team_with_flag(team: str) -> str:
    flag = COUNTRY_FLAGS.get(team, "🏳")
    return f"{flag} {escape(team_ru(team))}"


def match_result_line(match: dict) -> str:
    return (
        f"{team_with_flag(match['home_team'])} — "
        f"{team_with_flag(match['away_team'])} "
        f"{match['home_score']}:{match['away_score']}"
    )


def outcome_label(value: int, home_team: str, away_team: str) -> str:
    if value == 1:
        return f"победу {escape(team_ru(home_team))}"

    if value == -1:
        return f"победу {escape(team_ru(away_team))}"

    return "ничью"


async def get_finished_matches_by_group_round(matchday: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await (
            await db.execute(
                """
                SELECT
                    id,
                    home_team,
                    away_team,
                    home_score,
                    away_score
                FROM matches
                WHERE stage = 'GROUP_STAGE'
                  AND matchday = ?
                  AND status = 'finished'
                  AND home_score IS NOT NULL
                  AND away_score IS NOT NULL
                ORDER BY start_time
                """,
                (matchday,),
            )
        ).fetchall()

    return rows_to_matches(rows)


async def get_finished_matches_by_stages(stages: list[str]) -> list[dict]:
    if not stages:
        return []

    placeholders = ",".join("?" for _ in stages)

    async with aiosqlite.connect(DB_PATH) as db:
        rows = await (
            await db.execute(
                f"""
                SELECT
                    id,
                    home_team,
                    away_team,
                    home_score,
                    away_score
                FROM matches
                WHERE stage IN ({placeholders})
                  AND status = 'finished'
                  AND home_score IS NOT NULL
                  AND away_score IS NOT NULL
                ORDER BY start_time
                """,
                stages,
            )
        ).fetchall()

    return rows_to_matches(rows)


def rows_to_matches(rows) -> list[dict]:
    return [
        {
            "id": row[0],
            "home_team": row[1],
            "away_team": row[2],
            "home_score": row[3],
            "away_score": row[4],
        }
        for row in rows
    ]


async def get_approved_users() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await (
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

    return [
        {
            "user_id": row[0],
            "display_name": row[1],
            "username": row[2],
            "first_name": row[3],
        }
        for row in rows
    ]


async def get_predictions_for_matches(match_ids: list[int]) -> list[dict]:
    if not match_ids:
        return []

    placeholders = ",".join("?" for _ in match_ids)

    async with aiosqlite.connect(DB_PATH) as db:
        rows = await (
            await db.execute(
                f"""
                SELECT
                    p.user_id,
                    p.match_id,
                    p.home_score_pred,
                    p.away_score_pred
                FROM predictions p
                JOIN users u
                    ON u.id = p.user_id
                WHERE p.match_id IN ({placeholders})
                  AND u.is_approved = 1
                """,
                match_ids,
            )
        ).fetchall()

    return [
        {
            "user_id": row[0],
            "match_id": row[1],
            "home_pred": row[2],
            "away_pred": row[3],
        }
        for row in rows
    ]


async def get_overall_top(limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await (
            await db.execute(
                """
                SELECT
                    u.id,
                    u.display_name,
                    u.username,
                    u.first_name,
                    COALESCE(s.points, 0) AS points
                FROM users u
                LEFT JOIN scores s
                    ON s.user_id = u.id
                WHERE u.is_approved = 1
                ORDER BY
                    points DESC,
                    u.id ASC
                LIMIT ?
                """,
                (limit,),
            )
        ).fetchall()

    return [
        {
            "user_id": row[0],
            "display_name": row[1],
            "username": row[2],
            "first_name": row[3],
            "points": row[4],
        }
        for row in rows
    ]


def build_stats(
    users: list[dict],
    matches: list[dict],
    predictions: list[dict],
) -> tuple[list[dict], list[dict]]:
    matches_by_id = {match["id"]: match for match in matches}

    player_stats = {}

    for user in users:
        player_stats[user["user_id"]] = {
            **user,
            "points": 0,
            "exact": 0,
            "outcomes": 0,
            "misses": 0,
            "scored_matches": 0,
            "predictions_count": 0,
            "missed_predictions": len(matches),
        }

    match_stats = {}

    for match in matches:
        match_stats[match["id"]] = {
            **match,
            "predictions_count": 0,
            "points_getters": 0,
            "exact": 0,
            "outcome_votes": Counter(),
            "actual_outcome": outcome(
                match["home_score"],
                match["away_score"],
            ),
        }

    for prediction in predictions:
        user_id = prediction["user_id"]
        match_id = prediction["match_id"]

        if user_id not in player_stats:
            continue

        if match_id not in matches_by_id:
            continue

        match = matches_by_id[match_id]

        points = calculate_points(
            prediction["home_pred"],
            prediction["away_pred"],
            match["home_score"],
            match["away_score"],
        )

        player = player_stats[user_id]

        player["points"] += points
        player["predictions_count"] += 1
        player["missed_predictions"] -= 1

        if points == 2:
            player["exact"] += 1
            player["scored_matches"] += 1
        elif points == 1:
            player["outcomes"] += 1
            player["scored_matches"] += 1
        else:
            player["misses"] += 1

        match_row = match_stats[match_id]
        match_row["predictions_count"] += 1
        match_row["outcome_votes"][
            outcome(
                prediction["home_pred"],
                prediction["away_pred"],
            )
        ] += 1

        if points > 0:
            match_row["points_getters"] += 1

        if points == 2:
            match_row["exact"] += 1

    players = list(player_stats.values())

    players.sort(
        key=lambda item: (
            -item["points"],
            -item["exact"],
            -item["scored_matches"],
            item["missed_predictions"],
            item["user_id"],
        )
    )

    return players, list(match_stats.values())


def best_round_player(players: list[dict]) -> dict | None:
    if not players:
        return None

    return players[0]


def best_sniper(players: list[dict]) -> dict | None:
    candidates = [
        player for player in players
        if player["exact"] > 0
    ]

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            -item["exact"],
            -item["points"],
            item["missed_predictions"],
            item["user_id"],
        )
    )

    return candidates[0]


def most_stable_player(players: list[dict]) -> dict | None:
    candidates = [
        player for player in players
        if player["scored_matches"] > 0
    ]

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            -item["scored_matches"],
            -item["points"],
            -item["exact"],
            item["missed_predictions"],
            item["user_id"],
        )
    )

    return candidates[0]


def hardest_match(matches: list[dict]) -> dict | None:
    candidates = [
        match for match in matches
        if match["predictions_count"] > 0
    ]

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            item["points_getters"],
            item["exact"],
            -item["predictions_count"],
            item["id"],
        )
    )

    return candidates[0]


def easiest_match(matches: list[dict]) -> dict | None:
    candidates = [
        match for match in matches
        if match["predictions_count"] > 0
    ]

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            -item["points_getters"],
            -item["exact"],
            -item["predictions_count"],
            item["id"],
        )
    )

    return candidates[0]


def surprise_match(matches: list[dict]) -> dict | None:
    surprises = []

    for match in matches:
        if match["predictions_count"] == 0:
            continue

        if not match["outcome_votes"]:
            continue

        majority_outcome, majority_count = (
            match["outcome_votes"].most_common(1)[0]
        )

        if majority_outcome != match["actual_outcome"]:
            match["majority_outcome"] = majority_outcome
            match["majority_count"] = majority_count
            surprises.append(match)

    if not surprises:
        return None

    surprises.sort(
        key=lambda item: (
            -item["majority_count"],
            -item["predictions_count"],
            item["points_getters"],
            item["id"],
        )
    )

    return surprises[0]


def build_round_table_block(
    players: list[dict],
    matches_count: int
) -> str:
    text = "🏆 <b>Таблица этапа:</b>\n"

    if not players:
        return text + "Нет игроков для отображения.\n"

    for index, player in enumerate(players, start=1):
        name = format_player_name(player)

        text += (
            f"{medal(index)} {name} — "
            f"<b>{points_text(player['points'])}</b> · "
            f"🎯 {player['exact']} · "
            f"🟡 {player['outcomes']} · "
            f"❌ {player['misses']} · "
            f"прогнозов: {player['predictions_count']}/{matches_count}\n"
        )

    return text.rstrip()


def build_missing_block(players: list[dict]) -> str:
    missed = [
        player for player in players
        if player["missed_predictions"] > 0
    ]

    missed.sort(
        key=lambda item: (
            -item["missed_predictions"],
            item["user_id"],
        )
    )

    text = "⏳ <b>Пропущенные прогнозы:</b>\n"

    if not missed:
        return text + "Все игроки закрыли этап без пропусков."

    for player in missed:
        text += (
            f"• {format_player_name(player)} — "
            f"{player['missed_predictions']}\n"
        )

    return text.rstrip()


def build_overall_top_block(players: list[dict]) -> str:
    text = "📌 <b>Общая таблица после этапа:</b>\n"

    if not players:
        return text + "Нет данных."

    for index, player in enumerate(players, start=1):
        text += (
            f"{index}. {format_player_name(player)} — "
            f"{points_text(player['points'])}\n"
        )

    return text.rstrip()


def build_summary_text(
    title: str,
    users: list[dict],
    matches: list[dict],
    players: list[dict],
    match_stats: list[dict],
    predictions: list[dict],
    overall_top: list[dict],
) -> str:
    total_possible_predictions = len(users) * len(matches)
    total_predictions = len(predictions)

    fill_rate = (
        total_predictions / total_possible_predictions * 100
        if total_possible_predictions
        else 0
    )

    round_player = best_round_player(players)
    sniper = best_sniper(players)
    stable = most_stable_player(players)
    hard_match = hardest_match(match_stats)
    easy_match = easiest_match(match_stats)
    surprise = surprise_match(match_stats)

    total_exact = sum(player["exact"] for player in players)
    players_with_exact = sum(
        1 for player in players
        if player["exact"] > 0
    )

    text = (
        f"📊 <b>Итоги {title}</b>\n\n"

        "👥 <b>Участие:</b>\n"
        f"Игроков: <b>{len(users)}</b>\n"
        f"Матчей в этапе: <b>{len(matches)}</b>\n"
        f"Сделано прогнозов: <b>{total_predictions}</b> "
        f"из <b>{total_possible_predictions}</b>\n"
        f"Заполнение: <b>{percent_text(fill_rate)}</b>\n\n"

        f"{build_round_table_block(players, len(matches))}\n\n"
    )

    if round_player:
        text += (
            "🔥 <b>Игрок этапа:</b>\n"
            f"{format_player_name(round_player)} — "
            f"{points_text(round_player['points'])}, "
            f"🎯 {round_player['exact']} точных\n\n"
        )

    if sniper:
        text += (
            "🎯 <b>Снайпер этапа:</b>\n"
            f"{format_player_name(sniper)} — "
            f"{sniper['exact']} точных счетов\n\n"
        )

    if stable:
        text += (
            "🧱 <b>Самая стабильная игра:</b>\n"
            f"{format_player_name(stable)} — "
            f"очки в {stable['scored_matches']} "
            f"из {stable['predictions_count']} прогнозов\n\n"
        )

    if hard_match:
        text += (
            "😵 <b>Самый сложный матч:</b>\n"
            f"{match_result_line(hard_match)}\n"
            f"Очки получили: <b>{hard_match['points_getters']}</b> "
            f"из <b>{hard_match['predictions_count']}</b> · "
            f"точных: <b>{hard_match['exact']}</b>\n\n"
        )

    if easy_match:
        text += (
            "✅ <b>Самый предсказуемый матч:</b>\n"
            f"{match_result_line(easy_match)}\n"
            f"Очки получили: <b>{easy_match['points_getters']}</b> "
            f"из <b>{easy_match['predictions_count']}</b> · "
            f"точных: <b>{easy_match['exact']}</b>\n\n"
        )

    if surprise:
        text += (
            "🧨 <b>Матч-сюрприз:</b>\n"
            f"{match_result_line(surprise)}\n"
            f"Большинство: <b>{surprise['majority_count']}</b> "
            f"из <b>{surprise['predictions_count']}</b> — "
            f"{outcome_label(surprise['majority_outcome'], surprise['home_team'], surprise['away_team'])}\n\n"
        )

    text += (
        "🎯 <b>Точные счета:</b>\n"
        f"Всего точных счетов: <b>{total_exact}</b>\n"
        f"Игроков с точными счетами: <b>{players_with_exact}</b>\n\n"

        f"{build_missing_block(players)}\n\n"

        f"{build_overall_top_block(overall_top)}"
    )

    return text


async def build_group_round_stats_summary(
    matchday: int,
) -> tuple[str | None, str | None]:
    matches = await get_finished_matches_by_group_round(matchday)

    if not matches:
        return None, f"Нет завершённых матчей для тура {matchday}."

    users = await get_approved_users()

    if not users:
        return None, "Нет approved-пользователей."

    predictions = await get_predictions_for_matches(
        [match["id"] for match in matches]
    )

    players, match_stats = build_stats(
        users=users,
        matches=matches,
        predictions=predictions,
    )

    overall_top = await get_overall_top(limit=10)

    return (
        build_summary_text(
            title=round_title(matchday),
            users=users,
            matches=matches,
            players=players,
            match_stats=match_stats,
            predictions=predictions,
            overall_top=overall_top,
        ),
        None,
    )


async def build_stage_stats_summary(
    raw_stage: str,
) -> tuple[str | None, str | None]:
    stages, title = normalize_stage_arg(raw_stage)
    matches = await get_finished_matches_by_stages(stages)

    if not matches:
        return None, (
            f"Нет завершённых матчей для этапа {escape(title)}."
        )

    users = await get_approved_users()

    if not users:
        return None, "Нет approved-пользователей."

    predictions = await get_predictions_for_matches(
        [match["id"] for match in matches]
    )

    players, match_stats = build_stats(
        users=users,
        matches=matches,
        predictions=predictions,
    )

    overall_top = await get_overall_top(limit=10)

    return (
        build_summary_text(
            title=title,
            users=users,
            matches=matches,
            players=players,
            match_stats=match_stats,
            predictions=predictions,
            overall_top=overall_top,
        ),
        None,
    )


async def send_group_round_stats_summary(
    bot: Bot,
    matchday: int,
) -> tuple[bool, str | None]:
    text, error = await build_group_round_stats_summary(matchday=matchday)

    if error:
        return False, error

    if not text:
        return False, "Отчёт пустой."

    await send_message_to_all_users(
        bot=bot,
        text=text,
    )

    return True, None


async def send_stage_stats_summary(
    bot: Bot,
    raw_stage: str,
) -> tuple[bool, str | None]:
    text, error = await build_stage_stats_summary(raw_stage=raw_stage)

    if error:
        return False, error

    if not text:
        return False, "Отчёт пустой."

    await send_message_to_all_users(
        bot=bot,
        text=text,
    )

    return True, None