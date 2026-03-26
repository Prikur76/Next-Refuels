# Next-Refuels

`Next-Refuels` — корпоративная система учёта заправок автопарка:

- веб-ввод заправок и отчеты (Django);
- Telegram-бот для полевого ввода;
- синхронизация автопарка из `1C:Элемент`;

## Быстрый старт (локально)

### 1) Подготовить окружение

1. Скопируйте env:
   - PowerShell: `Copy-Item .env.example .env.dev`
2. Заполните минимум:
   - `SECRET_KEY`
   - `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`
   - `DATABASE_URL`
   - `TELEGRAM_BOT_TOKEN`
   - при необходимости алертов в Telegram: `TELEGRAM_ALERT_CHAT_ID`

### 1.1 Если запускаете Django без Docker

Docker сами ставит зависимости из `pyproject.toml`. Для локального запуска
без Docker:

1. Создайте/активируйте виртуальное окружение:
   - `python -m venv .venv`
   - PowerShell: `. .\.venv\Scripts\Activate.ps1`
2. Установите зависимости из `pyproject.toml`:
   - `python scripts/install-deps.py --upgrade-pip`
3. Примените миграции и запустите сервер:
   - `python manage.py migrate`
   - `python manage.py runserver 0.0.0.0:8000`

### 2) Запустить стек через Docker Compose

`bash scripts/test-local-deploy.sh`

Скрипт:

- поднимает `docker-compose.local.yml`;
- ожидает `web` в `healthy`;
- проверяет endpoints:
  - `http://localhost:8000/health/`
  - `http://localhost:5173/`

Если хотите руками:

- `docker compose -f docker-compose.local.yml up -d --build`
- `docker compose -f docker-compose.local.yml ps`
- `docker compose -f docker-compose.local.yml logs --tail=100 web`

### 3) Проверить функциональность

1. Веб (Next.js, локально в Docker обычно `http://localhost:5173`):
   - главная: `/`
   - ввод заправки: `/fuel/add/`
   - отчёты и журнал: `/fuel/reports/`
   - аналитика: `/analytics/`
2. Backend (Django): `http://localhost:8000` (`/admin/`, API `/api/v1/...`)
3. Telegram:
   - запускается командой `python manage.py runbot`
4. Синхронизация автопарка:
   - scheduler периодически запускает `python manage.py sync_cars_with_element`

## Документация

- `docs/SPEC.md` — продуктовая спецификация и сценарии.
- `docs/RUNBOOK.md` — деплой, SSL, импорт CSV, **аналитика дашборда** (срезы
  по источникам заправки, топливозаправщики).

## Полезные команды

- Запуск Telegram бота:
  - `python manage.py runbot`
- Синхронизация автопарка (1C):
  - `python manage.py sync_cars_with_element`
  - опции: `--check-only`, `--sample`, `--force`

## Проверка тестов (локально)

Для быстрой проверки MVP baseline прогоняйте Django-тесты:

Перед запуском убедитесь, что зависимости установлены. Рекомендуемый
способ (без Docker):

```powershell
python scripts/install-deps.py --upgrade-pip
```

Важно: для части тестов нужны пакеты для Excel и Telegram (они указаны в
`pyproject.toml`). Самые частые: `whitenoise`, `openpyxl`, `xlsxwriter`,
`python-telegram-bot`, `dj-database-url`. Если вы ставили не из
`pyproject.toml`, тесты могут падать на импортах.

```powershell
$env:DEBUG='True';
# Файл БД создаётся в текущем каталоге проекта
$env:DATABASE_URL='sqlite:///db.sqlite3';
$env:DB_SSL_REQUIRE='False';
python manage.py test --noinput -v 1
```

## Прод (контур)

Для prod используется `docker-compose.prod.yml`. Подробная процедура
описана в `docs/RUNBOOK.md`.

### Выкат на VPS (кратко)

1. На сервере: `git clone` (или перенос репозитория), каталог проекта с
   кодом и `docker-compose.prod.yml`.
2. Скопировать `.env.example` → `.env`, задать `SECRET_KEY`, `DEBUG=False`,
   `ALLOWED_HOSTS`, `DATABASE_URL` на рабочую PostgreSQL, все секреты
   интеграций, при необходимости `TELEGRAM_ALERT_CHAT_ID`.
3. `docker compose -f docker-compose.prod.yml up -d --build` (или ваш
   `deploy.sh`).
4. Проверить контейнеры (см. `docker-compose.prod.yml`), например:
   `next_refuels_web`, `next_refuels_nginx`, `next_refuels_frontend_prod`,
   `telegram_bot_prod`, `scheduler_prod`, `next_refuels_redis_prod`,
   `next_refuels_certbot` — и `GET /health/` у backend.
