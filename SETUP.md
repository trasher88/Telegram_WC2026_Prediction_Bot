# SETUP — быстрый запуск проекта

Инструкция по настройке и запуску Telegram-бота прогнозов ЧМ-2026.

---

## 1. Требования

Нужно:

- Python 3.11+;
- Telegram bot token от `@BotFather`;
- football-data.org API token;
- SQLite;
- доступ к серверу/VPS или локальной машине;
- Telegram ID администратора.

---

## 2. Установка зависимостей

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

---

## 3. Переменные окружения

Проект использует переменные окружения через `os.getenv()`.

Если в проект не добавлен `python-dotenv`, файл `.env` автоматически не загружается. Его нужно загружать через IDE, Docker, systemd, shell или добавить загрузку в `config.py`.

```env
BOT_TOKEN=...
FOOTBALL_DATA_API_TOKEN=...
ADMIN_IDS=123456789
APP_TIMEZONE=Europe/Moscow
WEB_ADMIN_API_KEY=...
DB_PATH=wc2026.db
ENABLE_API_SYNC=1
```

| Переменная | Назначение |
|---|---|
| `BOT_TOKEN` | Telegram bot token. |
| `FOOTBALL_DATA_API_TOKEN` | Токен football-data.org. |
| `ADMIN_IDS` | Telegram ID админов через запятую. |
| `APP_TIMEZONE` | Часовой пояс интерфейса и scheduler. Для проекта используется `Europe/Moscow`. |
| `WEB_ADMIN_API_KEY` | Ключ доступа к web admin. |
| `DB_PATH` | Путь к SQLite-базе. Например `wc2026.db` или `test_wc2026.db`. |
| `ENABLE_API_SYNC` | `1` — включить API sync, `0` — отключить API sync. |

---

## 4. Тестовый режим

Для локальных тестов:

```env
DB_PATH=test_wc2026.db
ENABLE_API_SYNC=0
```

В этом режиме:

- бот работает с тестовой базой;
- автоматический API sync отключён;
- можно безопасно тестировать `/set_score`, `/leaderboard`, `/form`, `/my_stats`;
- `/force_sync` должен быть заблокирован, чтобы не перезаписать тестовые данные.

---

## 5. Боевой режим

Для настоящего турнира:

```env
DB_PATH=wc2026.db
ENABLE_API_SYNC=1
APP_TIMEZONE=Europe/Moscow
```

Перед боевым запуском проверь, что в `scheduler.py` стоят реальные времена уведомлений:

```text
13:00 — daily digest
18:00 — missing predictions reminder
18:30 — admin report
```

---

## 6. Запуск бота

```bash
python main.py
```

Ожидаемо:

- создаётся или мигрируется SQLite-БД;
- бот стартует;
- в логах появляется `Bot started: @...`;
- scheduler готов;
- Telegram отвечает на `/start`.

---

## 7. Команды пользователей

| Команда | Назначение |
|---|---|
| `/start` | Запуск, регистрация, ввод турнирного имени. |
| `/rename` | Изменить турнирное имя. |
| `/help` | Правила турнира и список команд. |
| `/matches` | Расписание матчей. |
| `/predict` | Сделать или изменить прогноз. |
| `/my_predictions` | Мои прогнозы. |
| `/leaderboard` | Таблица лидеров. |
| `/form` | Форма за последние 10 завершённых прогнозов. |
| `/my_stats` | Персональная статистика игрока. |

---

## 8. Команды администратора

| Команда | Назначение |
|---|---|
| `/admin` | Меню админ-команд. |
| `/force_sync` | Ручная синхронизация API. Должна быть заблокирована при `ENABLE_API_SYNC=0`. |
| `/set_score <match_id> <home> <away>` | Ручная установка результата матча. |
| `/rebuild_scores` | Полный пересчёт очков. |
| `/match_info <match_id>` | Диагностика матча. |
| `/match_ids` | ID матчей по выбранной стадии/туру. |
| `/broadcast <text>` | Рассылка всем пользователям. |
| `/users` | Статистика пользователей. |
| `/stats` | Админ-статистика турнира. |
| `/test_lock <match_id>` | Тест сообщения о закрытии прогнозов. |

---

## 9. Правила турнира

### Очки

| Прогноз | Очки |
|---|---:|
| Точный счёт | 2 |
| Угадан исход | 1 |
| Промах | 0 |

### Тай-брейк leaderboard

Если у игроков одинаковое количество очков, выше будет тот, у кого больше точных счетов.

### Блокировка прогнозов

Прогноз можно поставить или изменить до закрытия приёма. Приём закрывается за 5 минут до начала матча.

### Плей-офф и пенальти

Если матч дошёл до серии пенальти, победителю серии добавляется `+1` гол.

```text
1:1 после игры, первая команда выиграла пенальти -> 2:1 для прогнозов
1:1 после игры, вторая команда выиграла пенальти -> 1:2 для прогнозов
```

---

## 10. Игровой день и уведомления

Игровой день считается по Москве:

```text
13:00 текущего дня — 12:59 следующего дня
```

| Время МСК | Что происходит |
|---|---|
| 13:00 | Всем игрокам список матчей игрового дня. |
| 18:00 | Напоминание тем, кто ещё не поставил все прогнозы. |
| 18:30 | Админ-отчёт по прогнозам. |

---

## 11. Web admin

Запуск:

```bash
uvicorn web_admin:app --host 127.0.0.1 --port 8000
```

Проверка:

```bash
curl -H "X-API-Key: your-key" http://127.0.0.1:8000/matches
curl -H "X-API-Key: your-key" http://127.0.0.1:8000/scores
```

Без корректного `X-API-Key` доступ должен быть запрещён.

---

## 12. Проверка перед запуском

```bash
python -m compileall -q .
python test_api.py
python main.py
```

Затем в Telegram:

```text
/start
/help
/matches
/predict
/my_predictions
/leaderboard
/form
/my_stats
```

Админом:

```text
/admin
/match_ids
/match_info <match_id>
/set_score <match_id> 2 1
/rebuild_scores
/stats
/users
```

---

## 13. Что не класть в архив/репозиторий

Не включать:

- `.env`;
- реальные SQLite-базы `*.db`;
- `.idea/`;
- `.venv/`;
- `__pycache__/`;
- токены;
- приватные backup-файлы.

Если токен попал в архив или чат, его лучше перевыпустить.

---

## 14. Рекомендации для продакшена

- запускать через `systemd`, Docker или process manager;
- делать регулярные backup SQLite;
- хранить `.env` вне git;
- логировать ошибки в файл;
- ограничить web admin сильным `WEB_ADMIN_API_KEY`;
- перед турниром проверить API и `/force_sync`;
- держать тестовую базу отдельно от боевой.
