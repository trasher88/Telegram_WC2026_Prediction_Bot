from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from utils import texts as T


POPULAR_SCORES = [
    (0, 0), (1, 0), (1, 1), (0, 1), (2, 0),
    (2, 1), (2, 2), (1, 2), (0, 2), (3, 0),
    (3, 1), (3, 2), (2, 3), (1, 3), (0, 3)
]


STAGE_BUTTONS = [
    (T.LAST_32, "LAST_32"),
    (T.LAST_16, "LAST_16"),
    (T.QUARTER_FINALS, "QUARTER_FINALS"),
    (T.SEMI_FINALS, "SEMI_FINALS"),
    (T.THIRD_PLACE, "THIRD_PLACE"),
    (T.FINAL, "FINAL"),
]


GROUP_ROUND_BUTTONS = [
    (T.ROUND_1, 1),
    (T.ROUND_2, 2),
    (T.ROUND_3, 3),
]


STAGE_TITLES = {
    "LAST_32": "1/16 финала",
    "LAST_16": "1/8 финала",
    "QUARTER_FINALS": "1/4 финала",
    "SEMI_FINALS": "Полуфинал",
    "THIRD_PLACE": "Матч за 3-е место",
    "FINAL": "Финал",
}


def tournament_stage_keyboard(group_prefix: str, stage_prefix: str) -> InlineKeyboardMarkup:
    rows = []

    for text, round_number in GROUP_ROUND_BUTTONS:
        rows.append([
            InlineKeyboardButton(
                text=text,
                callback_data=f"{group_prefix}{round_number}"
            )
        ])

    for text, stage in STAGE_BUTTONS:
        rows.append([
            InlineKeyboardButton(
                text=text,
                callback_data=f"{stage_prefix}{stage}"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def prediction_score_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    row = []

    for home, away in POPULAR_SCORES:
        row.append(
            InlineKeyboardButton(
                text=f"{home}:{away}",
                callback_data=f"pred_score:{home}:{away}"
            )
        )

        if len(row) == 3:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    buttons.append(
        [
            InlineKeyboardButton(
                text=T.ANOTHER_SCORE,
                callback_data="pred_score:custom"
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)
