# Next-Refuels — Product and Technical Specification

## 1. Назначение проекта

`Next-Refuels` — корпоративная система учёта заправок автопарка, состоящая из:

- веб-приложения на Django (ввод данных, отчеты, админ-панель);
- Telegram-бота для оперативного внесения заправок;
- фоновых задач синхронизации автомобилей с внешней системой `1C:Элемент`;

Основная бизнес-цель: централизованный и контролируемый учет заправок с
разграничением прав по ролям и прозрачной отчетностью.

## 2. Границы системы

### In scope

- управление справочниками: автомобили, регионы, пользователи;
- ввод заправок (веб + Telegram);
- просмотр отчетов по заправкам;
- логирование действий пользователей;
- синхронизация автопарка с внешним API;

### Out of scope

- бухгалтерские расчеты и биллинг;
- телеметрия/трекинг топлива с датчиков;
- мобильное приложение (кроме Telegram-бота);
- сложная BI-аналитика (DWH/OLAP).

## 3. Основные роли и права

- `Заправщик`: ввод заправок.
- `Менеджер`: ввод заправок + просмотр отчетов.
- `Администратор`: полный доступ, включая администрирование и управление
пользователями.

Веб-часть и бот ориентируются на групповые права Django.

## 4. Архитектура

### Технологический стек

- Python 3.12+
- Django 5.x
- django-ninja (подготовлено в проекте)
- python-telegram-bot
- aiohttp (внешние HTTP-интеграции)
- PostgreSQL (prod), SQLite/PostgreSQL (dev сценарии)
- Redis (prod cache)
- Docker Compose + Nginx + Gunicorn/Uvicorn

### Компоненты

- `next_refuels/` — Django project (settings, urls, ASGI/WSGI).
- `core/` - бизнес-логика:
  - `models/` - доменные сущности;
  - `views.py` - веб-интерфейс;
  - `refuel_bot/` - логика Telegram-бота;
  - `clients/` - клиенты внешних API;
  - `services/` - сервисы интеграций;
  - `management/commands/` - фоновые и операционные команды.
- `docker-compose*.yml` - локальное и прод-окружения.
- `nginx/templates/` — шаблон reverse proxy и SSL; `DOMAIN` из `.env` подставляется при старте контейнера `nginx`.
- `frontend/` — веб-клиент на Next.js для ввода и аналитики.

### Внешние интеграции

- `1C:Элемент API`: получение и синхронизация автомобилей.
- Telegram Bot API: пользовательский интерфейс для полевого ввода.

## 5. Доменная модель (ключевые сущности)

- `User`:
  - кастомный пользователь Django с `telegram_id`, привязкой к региону.
- `Car`:
  - автомобиль компании, статус активности/архива, регион.
- `FuelRecord`:
  - факт заправки (авто, сотрудник, объем, тип топлива, источник, статус
  подтверждения, исторический регион/подразделение на момент записи).
- `Region`:
  - территориальная структура.
- `SystemLog`:
  - аудит пользовательских и системных действий.

## 6. Функциональные требования (MVP текущей реализации)

1. Пользователь с валидной ролью может добавить запись о заправке.
2. Система валидирует авто и значения объема.
3. Отчеты показывают последние записи заправок с ключевыми атрибутами.
4. Telegram-бот поддерживает диалоговый сценарий ввода.
5. Система синхронизирует актуальный список автомобилей из `1C:Элемент`.
6. Для операций синхронизации и ошибок ведется лог.
7. Доступность приложения проверяется через health endpoint.

## 7. Нефункциональные требования

- Безопасность:
  - аутентификация для веб-доступа;
  - разграничение прав по группам;
  - изоляция секретов через `.env` и `local_secrets`.
- Надежность:
  - healthcheck контейнеров;
  - циклический scheduler для синхронизации;
  - логирование ошибок.
- Эксплуатация:
  - запуск в Docker Compose;
  - отдельные профили для local/prod.

## 8. Конфигурация и окружения

### Local

- основной файл оркестрации: `docker-compose.local.yml`;
- сервисы: `frontend`, `web`, `bot`, `scheduler`;
- фронтенд в отдельном сервисе `frontend` (`next dev`, см. `frontend/package.json`);
- обязательный env-файл: `.env.dev` (бот и scheduler также используют его);
- быстрый цикл разработки и проверок;
- smoke-тест локального разворачивания: `scripts/test-local-deploy.sh`.

### Production

- основной файл оркестрации: `docker-compose.prod.yml`;
- сервисы: `frontend`, `web`, `nginx`, `certbot`, `redis`, `bot`, `scheduler`;
- SSL-терминация на Nginx;
- Gunicorn + Uvicorn worker для web;
- автоматическое продление SSL:
  - `certbot` запускает `certbot renew` каждые 12 часов;
  - `certbot` имеет healthcheck через `scripts/check-cert-expiry.sh`;
  - `nginx` периодически выполняет `reload` для подхвата новых сертификатов.

### Локальная проверка перед сервером (Docker)

1. Подготовить env:
   - `cp .env.example .env.dev` (Linux/macOS) или
   - `Copy-Item .env.example .env.dev` (PowerShell).
2. Заполнить минимум: `SECRET_KEY`, `POSTGRES_*`, `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`.
3. Запустить smoke-тест:
   - `bash scripts/test-local-deploy.sh` (Linux/macOS/Git Bash),
   - либо выполнить шаги вручную:
     - `docker compose -f docker-compose.local.yml up -d --build`,
     - проверка `http://localhost:8000/health/`,
     - проверка `http://localhost:5173/`.
4. Проверить статусы:
   - `docker compose -f docker-compose.local.yml ps`,
   - `docker compose -f docker-compose.local.yml logs --tail=100 web`.

### Доступ к базе данных и проверка прав

При старте контейнеров выполняются несколько уровней проверки:

- `scripts/wait-for-db.py` проверяет только TCP-доступность
  `POSTGRES_HOST:POSTGRES_PORT`. Это подтверждает, что порт открыт,
  но не гарантирует права на схему/таблицы.
- Django выполняет `python manage.py migrate --noinput` и другие
  операции в `scripts/entrypoint.dev.sh` (dev/local). Если у роли приложения
  нет прав на схему `public`, контейнер `web` падает с
  `django.db.utils.ProgrammingError: permission denied for schema public`.
- `deploy.sh` дополнительно делает явную проверку подключения к Postgres
  через `psycopg2.connect` (использует `POSTGRES_DB/USER/PASSWORD/HOST`),
  после чего запускает миграции и collectstatic.

Используемая роль определяется env:

- `DATABASE_URL` (основной источник для Django) и/или
- `POSTGRES_USER`/`POSTGRES_PASSWORD` (используются в `deploy.sh`
  и в `wait-for-db`/настройках контейнера при тестах).

SSL-требования задаются через `DB_SSL_REQUIRE` (передается в Django как
`ssl_require`). При этом `scripts/wait-for-db.py` проверяет только TCP,
а реальное подключение (в т.ч. SSL и права) происходит при миграциях
и/или `psycopg2.connect`.

Обычно в конфигурации используется пользователь `refuelbot` для БД
  `test_refuelbot`.

#### Необходимые привилегии для роли приложения

Выполнять под `owner`/`superuser` БД в целевой базе:

```sql
GRANT CONNECT ON DATABASE <db> TO <user>;
GRANT USAGE, CREATE ON SCHEMA public TO <user>;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO <user>;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO <user>;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT ALL ON TABLES TO <user>;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT ALL ON SEQUENCES TO <user>;
```

Если проблема повторяется, дополнительно проверьте/попробуйте сменить
owner схемы:

```sql
ALTER SCHEMA public OWNER TO <user>;
```

#### Верификация прав

Подключиться как `<user>` и выполнить:

```sql
CREATE TABLE IF NOT EXISTS public.__perm_test(id int);
DROP TABLE IF EXISTS public.__perm_test;
```

## 9. Точки входа и интерфейсы

### Веб-маршруты

- `/` - главная страница;
- `/fuel/add/` - добавление заправки;
- `/fuel/reports/` - отчеты;
- `/access` - управление доступом (только менеджер/администратор);
- `/bot` - привязка Telegram-бота (показывается в навигации только при
  отсутствии привязки);
- `/health/` - health-check JSON;
- `/admin/` - административный интерфейс.

### API v1 (django-ninja и смежные view)

Префикс Ninja: `path("api/v1/", api.urls)` в `next_refuels/urls.py`. Объект API:
`core.api.api` (`NinjaAPI`, title `Next-Refuels API`, version `1.0.0`).

**Swagger / OpenAPI:** интерактивная UI — `GET /api/v1/docs` (например
`http://localhost:8000/api/v1/docs` при локальном `runserver`). В схеме
заданы: общее описание API и теги (`auth`, `fuel`, `reports`, `access`,
`analytics`), у операций — `summary` и `description`, у параметров и полей
схем — подсказки через `Query`, `Path`, `Body` и `Field(..., description=)`
в `core/api.py` и `core/schemas.py`. Скачивание аналитики XLSX документируется
отдельным ответом `200` с `format: binary` у `GET /api/v1/analytics/export`.

Все перечисленные ниже методы, кроме экспорта CSV/XLSX, реализованы в
`core/api.py`. Экспорт отчётов — отдельные Django-view в `core/api_views.py`
(те же query-параметры фильтров, что у отчётов в вебе).

Общие правила:

- авторизация: session cookie (после логина); без сессии — `401`;
- для мутаций из браузера нужен CSRF: сначала `GET /api/v1/auth/csrf`;
- часовой пояс клиента для части сценариев заправщика: заголовок
  `X-Client-Timezone` (IANA, например `Europe/Moscow`); пустое значение —
  используется `TIME_ZONE` Django.

#### Auth

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/api/v1/auth/csrf` | Выставить CSRF cookie (`ensure_csrf_cookie`), тело `{"ok": true}`. |
| GET | `/api/v1/auth/me` | Профиль: `UserMeOut` (в т.ч. `telegram_linked`, `groups`, `app_timezone`, `has_my_editable_fuel_records`). Query: `client_tz` (опционально). |
| POST | `/api/v1/auth/telegram/link-code` | Одноразовый код привязки Telegram (`TelegramLinkCodeOut`). Требуется право ввода. |
| POST | `/api/v1/auth/password/setup` | Первая смена пароля (`PasswordSetupIn` → `PasswordSetupOut`), только если `must_change_password`. |

#### Автомобили и заправки

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/api/v1/cars` | Список активных авто (`CarOut[]`). Query: `query` (поиск по госномеру), `limit` (1…100, по умолчанию 20). |
| POST | `/api/v1/fuel-records` | Создание заправки (`FuelRecordIn` → `FuelRecordOut`). |
| GET | `/api/v1/fuel-records/recent` | Последние записи (глобально). Query: `limit`. |
| GET | `/api/v1/fuel-records/mine` | Записи заправщика за скользящее окно (см. `FuelService`). Только группа заправщика. |
| PATCH | `/api/v1/fuel-records/{record_id}` | Частичное обновление (`FuelRecordPatchIn` → `FuelRecordOut`). |

Тела запросов (схемы Ninja в `core/api.py`):

- **`FuelRecordIn`**: `car_id`, `liters`, `fuel_type` (`GASOLINE` \| `DIESEL`),
  `source` (`CARD` \| `TGBOT` \| `TRUCK`), `notes` (строка, по умолчанию пустая).
- **`FuelRecordPatchIn`**: все поля опциональны: `car_id`, `liters`,
  `fuel_type`, `source`, `notes`, `filled_at` (datetime), `reporting_status`
  (`ACTIVE` \| `EXCLUDED_DELETION` — см. `FuelRecord.ReportingStatus`).

Ответ **`FuelRecordOut`**: идентификаторы, `car_state_number`,
`car_is_fuel_tanker`, объём, тип топлива, источник, `filled_at` (ISO),
`employee_name`, `region_name`, `reporting_status`, `notes`.

#### Отчёты (журнал и сводки)

Общие query-фильтры (где применимо): `from_date`, `to_date` (date),
`region_id`, `region` (подстрока имени), `employee`, `car_id`,
`car_state_number`, `source`. Для не-админов `region_id` нормализуется
по scope пользователя (`FuelService.normalized_reports_region_id`).

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/api/v1/reports/summary` | Сводка: `total_records`, `total_liters`, `avg_liters` (`SummaryOut`). |
| GET | `/api/v1/reports/filters` | Списки для фильтров UI: `employees`, `regions` (`ReportsFiltersOut`). |
| GET | `/api/v1/reports/records` | Страница журнала (`RecordsPageOut`: `items`, `total`, `has_next`, `next_cursor`). Пагинация: `offset` + `limit` (до 200) **или** `cursor` (base64, при `cursor` поле `total` может быть 0). |
| GET | `/api/v1/reports/access-events` | Аудит access-действий (`AccessLogOut[]`). Query: `limit` (до 200). Не-админы видят только свои события. |
| GET | `/api/v1/reports/export/csv` | Скачивание CSV (не Ninja). |
| GET | `/api/v1/reports/export/xlsx` | Скачивание XLSX (не Ninja). |

#### Управление доступом (scoped RBAC)

Базовый префикс `/api/v1/access/`. Детали прав — `UserAccessService`.

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/api/v1/access/users` | Список пользователей. Query: `show_all` (включая неактивных). |
| POST | `/api/v1/access/users` | Создание заправщика (`AccessUserCreateIn` → `AccessUserCreateOut`). |
| PATCH | `/api/v1/access/users/{user_id}` | Активация/деактивация (`AccessStatusPatchIn`). |
| PATCH | `/api/v1/access/users/{user_id}/role` | Назначение роли (`AccessRolePatchIn`: `Заправщик` \| `Менеджер` \| `Администратор`). |
| POST | `/api/v1/access/users/{user_id}/reset-password` | Сброс пароля (временный в ответе `AccessPasswordOut`). |
| PATCH | `/api/v1/access/users/{user_id}/password` | Задать пароль или сгенерировать временный (`AccessPasswordPatchIn`). |
| PATCH | `/api/v1/access/users/{user_id}/scope` | Смена региона scope (`AccessScopePatchIn`). |
| PATCH | `/api/v1/access/users/{user_id}/profile` | Профиль: ФИО, email, телефон, регион (`AccessUserProfilePatchIn`). |
| GET | `/api/v1/access/regions` | Справочник регионов для UI (`RegionOut[]`). |

#### Аналитика

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/api/v1/analytics/stats` | Дашборд (`AnalyticsDataOut` в `core/schemas.py`): `by_day`, `by_day_region`, `refuel_sources`, `refuel_channels`, `recent_records`, `by_employee`, `by_car`, `by_car_fuel_tankers`. Query: `start_date`, `end_date`, `region_id`. |
| GET | `/api/v1/analytics/export` | Выгрузка XLSX по тем же фильтрам; бинарный ответ `Content-Disposition: attachment`. |

Семантика срезов аналитики согласована с `docs/ARCHITECTURE.md` (раздел про
дашборд и `_analytics_dashboard_channel_records_qs`).

### Команды управления

- `python manage.py runbot` - запуск Telegram-бота;
- `python manage.py sync_cars_with_element` - синхронизация автопарка;
- `python manage.py create_superuser` - создание админа из env;
- `python manage.py migrate`, `collectstatic` - операционные задачи Django.

### Команды разработки

- `uv run ruff check manage.py core next_refuels scripts` — линт backend-кода;
- `uv run ruff format core next_refuels scripts` — форматирование backend-кода;
- `npm run dev` (в `frontend/`) — локальный запуск Next.js (dev-сервер).

## 10. Известные ограничения и риски

1. Отсутствует полноценно заполненный `README.md` (низкая onboarding-готовность).
2. Тестовое покрытие минимальное (в текущем виде фактически отсутствует).
3. Зависимости берутся только из `pyproject.toml`.
4. В конфигурации присутствуют жестко заданные инфраструктурные значения
  (например, домен в Nginx), что ухудшает переносимость.
5. Деплой-скрипт содержит потенциально опасные git-операции (`reset --hard`).
6. Обнаружен риск синтаксической ошибки в клиенте синхронизации
  (`core/clients/element_car_client.py`, блок итогового логирования).

## 11. План первоочередных улучшений

### P0 (критично)

- Исправить потенциальные runtime/syntax-проблемы в синхронизации с `1C:Элемент`.
- Убрать/пересмотреть destructive-часть в `deploy.sh`.
- Ввести smoke-тесты на ключевые потоки (веб-ввод, бот-ввод, sync command).

### P1 (важно)

- Подготовить полноценный `README.md` и runbook эксплуатации.
- Нормализовать dependency management (единый источник версий).
- Вынести окружение и доменные настройки в переменные без хардкода.

### P2 (развитие)

- Расширить публичный/партнёрский API (webhooks, отдельные токены) поверх
  текущего контура django-ninja.
- Добавить метрики/наблюдаемость (latency, error rate, sync duration).
- Расширить ролевую модель и аудит событий.

## 12. Критерии приемки для текущего baseline

- Проект поднимается локально через Docker Compose.
- Веб-интерфейс доступен и отвечает по `/health/`.
- Бот запускается и принимает команды авторизованного пользователя.
- Синхронизация с `1C:Элемент` выполняется по команде без аварийного падения.
- Записи заправок сохраняются и отображаются в отчетах.

## 13. Roadmap документации

Следующие документы (после этого базового SPEC):

- `ARCHITECTURE.md` - C4/компоненты и диаграммы потоков;
- `RUNBOOK.md` - эксплуатация, инциденты, восстановление;
- `SECURITY.md` - модель угроз, секреты, hardening;
- `TESTPLAN.md` - тестовая стратегия и матрица покрытий.

## 14. AuthN/AuthZ дополнение

- Локальная auth усилена policy-настройками сессии/cookie и throttling
  попыток входа.
- Реализован scoped RBAC для менеджеров:
  - менеджер управляет пользователями только в пределах своего региона;
  - администратор имеет глобальный охват.
- Добавлены access-management API (см. таблицу в разделе 9):
  - `GET/POST /api/v1/access/users`,
  - `PATCH /api/v1/access/users/{id}` (активность),
  - `PATCH /api/v1/access/users/{id}/role`,
  - `POST /api/v1/access/users/{id}/reset-password`,
  - `PATCH .../password`, `PATCH .../scope`, `PATCH .../profile`,
  - `GET /api/v1/access/regions`.
- Добавлен аудит access-событий и endpoint
  `/api/v1/reports/access-events`.
- В веб-клиенте добавлен раздел `Доступ` для менеджеров/админов.
- В веб-клиенте добавлен маршрут `/bot` для self-service привязки Telegram.
- В API `GET /api/v1/auth/me` добавлено поле `telegram_linked`:
  - `true` — Telegram уже привязан к учетной записи;
  - `false` — привязки нет, в навигации показывается кнопка `Бот`.
- Правила навигации (desktop + mobile):
  - `Заправщик`: видит `Бот` только если `telegram_linked=false`, пункт
    `Доступ` не показывается;
  - `Менеджер`/`Администратор`: всегда видят `Доступ`, а `Бот` только если
    `telegram_linked=false`.
- При смене `is_active` пользователя очищается кэш Telegram middleware
  (`bot_user:<telegram_id>`), чтобы после реактивации доступ бота
  восстанавливался без ожидания TTL.
- Подготовлен SSO-readiness слой (`local` сейчас, `oidc/saml` как следующий
  этап) через abstraction identity provider.
