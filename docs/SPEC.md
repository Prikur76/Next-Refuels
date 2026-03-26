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
- `/health/` - health-check JSON;
- `/admin/` - административный интерфейс.

### API v1 (клиент Next.js и backend)

- `/api/v1/auth/me` - профиль текущего пользователя;
- `/api/v1/cars` - поиск активных автомобилей;
- `/api/v1/fuel-records` - создание записи заправки;
- `/api/v1/fuel-records/recent` - последние записи;
- `/api/v1/reports/summary` - агрегированная сводка;
- `/api/v1/reports/records` - журнал с фильтрами и пагинацией;
- `/api/v1/reports/export/csv`, `/api/v1/reports/export/xlsx` - экспорт отчетов.

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

- Добавить API-контур (например, через django-ninja) для интеграций и внешней
аналитики.
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
- Добавлены access-management API:
  - `/api/v1/access/users` (list/create),
  - `/api/v1/access/users/{id}` (activate/deactivate),
  - `/api/v1/access/users/{id}/assign-fueler`,
  - `/api/v1/access/users/{id}/reset-password`.
- Добавлен аудит access-событий и endpoint
  `/api/v1/reports/access-events`.
- В веб-клиенте добавлен раздел `Доступ` для менеджеров/админов.
- Подготовлен SSO-readiness слой (`local` сейчас, `oidc/saml` как следующий
  этап) через abstraction identity provider.
