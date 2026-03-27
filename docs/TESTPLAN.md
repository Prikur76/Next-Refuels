# Next-Refuels — план тестирования

## Цель

План описывает проверку MVP baseline:

- веб-ввод и отчеты заправок;
- Telegram-диалоговый ввод заправок;
- синхронизация автопарка с `1C:Элемент`;
- аудит/логирование и healthcheck;
- базовая устойчивость и корректность авторизации.

## Объем тестирования

### Уровни

1. Unit-тесты сервисного слоя и доменных ограничений.
2. Интеграционные тесты API (Django test client).
3. E2E smoke: Docker Compose startup + проверка `/health/`.
4. Ручные сценарии Telegram (диалог).
5. Тесты интеграций (частично ручные/через заглушки внешних API).

### Что уже покрыто

Тесты вынесены в пакет `core/tests/` и разбиты по модулям:

- `core/tests/test_api.py`: smoke по `POST /api/v1/fuel-records` и
  `GET /api/v1/cars`;
- `core/tests/test_access_api.py`: RBAC/доступ и управление
  паролями в `access-management` API, включая очистку bot-кэша при
  смене `is_active`;
- `core/tests/test_scenarios_api.py`: сценарии `auth`, `cars`,
  `fuel-records`, `reports/*` и `analytics/*`, включая `telegram_linked`
  в `auth/me`;
- `core/tests/test_export_and_commands.py`:
  экспорт (CSV/XLSX) и `management commands` (`runbot`,
  `sync_cars_with_element`).

## Матрица тестов (baseline)

### 1. Авторизация и роли

- Проверить, что пользователь с группой `Заправщик` может создать
  `FuelRecord` через web и API.
- Проверить, что `Менеджер` может открыть отчеты и доступ к
  `reports/*`, но не может выполнять действия уровня “другого”
  региона в access-management API.
- Проверить, что `Администратор` имеет глобальный охват.
- Проверить ответ `GET /api/v1/auth/me`:
  - при `telegram_id is null` возвращается `telegram_linked=false`;
  - при заполненном `telegram_id` возвращается `telegram_linked=true`.

### 1.1 Навигация (desktop + mobile)

- `Заправщик` без привязки: видит пункт `Бот`, не видит пункт `Доступ`.
- `Заправщик` с привязкой: не видит `Бот`, не видит `Доступ`.
- `Менеджер`/`Администратор` без привязки: видят `Доступ` и `Бот`.
- `Менеджер`/`Администратор` с привязкой: видят `Доступ`, не видят `Бот`.

### 2. Валидация входных данных

- Невалидный `liters` (не число, `<=0`, слишком большое значение) должен
  приводить к ошибке (web/form validation или API `400`).
- Невалидные `fuel_type` и `source` должны быть отклонены.
- Невалидный `car_id` (неактивная машина) должен отклоняться.

### 3. Отчеты

- После создания нескольких записей `recent` и `reports/summary`
  должны возвращать корректные агрегаты.
- `reports/records` должна поддерживать фильтры и пагинацию по курсору.

### 4. Telegram-бот

- Привязка Telegram аккаунта по коду из `/start <code>`.
- Ввод последовательности: госномер -> литры -> способ.
- Отказ при попытке начать сценарий без привязки/прав.
- Смена `is_active` в access-management API должна сразу влиять на доступ
  в боте (без ожидания TTL кэша `bot_user:<telegram_id>`).

**Автотесты:** в `core/tests/test_export_and_commands.py` тест
`test_runbot_calls_run_bot` проверяет, что `manage.py runbot` вызывает
`run_bot` (без реального polling и без сети к Telegram).

**Ручной smoke с Bot API:** при необходимости проверить токен и long
polling локально — `python manage.py runbot` с валидным
`TELEGRAM_BOT_TOKEN` в окружении (см. `.env.example`). Отдельный скрипт
в корне репозитория не используется: он дублировал бы этот сценарий и
не входил в CI.

### 5. Синхронизации

- `sync_cars_with_element`:
  - запускается из scheduler без падения контейнера;
  - успех и ошибка пишутся в `SystemLog`.
## Smoke-test сценарий (локально)

1. Подготовить env:
   - Linux/macOS: `cp .env.example .env.dev`
   - PowerShell: `Copy-Item .env.example .env.dev`
2. Запустить:
   - `bash scripts/test-local-deploy.sh`
3. Проверить в конце:
   - `http://localhost:8000/health/` возвращает `{"status":"healthy", ...}`.
   - веб-интерфейс (Next.js) доступен на `http://localhost:5173/`.

## Регресс-требования

Перед релизом baseline:

- выполнить smoke-тест через Docker Compose;
- прогнать Django тесты локально:
  - рекомендуется SQLite без прав на Postgres:
    `python manage.py test --noinput`;
  - если тесты запускаются на Postgres, убедитесь, что user приложения
    может создавать тестовую БД и выполнять миграции;
- проверить, что ключевые API endpoints доступны:
  - `/api/v1/auth/csrf`
  - `/api/v1/auth/me`
  - `/api/v1/fuel-records`
  - `/api/v1/reports/summary`

## Как запускать тесты локально (рекомендуется)

Принудительно переключить Django на SQLite (чтобы не упираться в права
Postgres), например:

```powershell
$env:DEBUG='True'
$env:DATABASE_URL='sqlite:///E:\AI_AGENT\CURSOR_AI\Next-Refuels\db.sqlite3'
$env:DB_SSL_REQUIRE='False'
python manage.py test --noinput -v 1
```

Если всё равно хотите Postgres, то запуск выглядит так:

```powershell
python manage.py test --noinput -v 1
```

При ошибках прав на создание тестовой БД/таблиц — настройте `GRANT` для
вашего пользователя БД (см. `docs/RUNBOOK.md`).

## Предварительные зависимости (для локального запуска)

Перед прогоном тестов убедитесь, что установлены зависимости из
`pyproject.toml` (без Docker):

```powershell
python scripts/install-deps.py --upgrade-pip
```
