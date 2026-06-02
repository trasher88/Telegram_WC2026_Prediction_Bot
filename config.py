import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Не задана переменная окружения {name}. "
            f"Скопируйте .env.example в .env или задайте переменную на сервере."
        )
    return value


TOKEN = _get_required_env("BOT_TOKEN")
API_TOKEN = _get_required_env("FOOTBALL_DATA_API_TOKEN")

ADMIN_IDS = {
    int(user_id.strip())
    for user_id in os.getenv("ADMIN_IDS", "").split(",")
    if user_id.strip()
}

APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Europe/Moscow")

# для теста БД
ENABLE_API_SYNC = os.getenv("ENABLE_API_SYNC", "1").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

WEB_ADMIN_API_KEY = os.getenv("WEB_ADMIN_API_KEY")
