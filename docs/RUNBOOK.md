# RUNBOOK

## 1. Назначение

`RUNBOOK.md` описывает эксплуатационные процедуры для проекта
`Next-Refuels`:

- локальная проверка Docker-разворачивания перед деплоем;
- базовый прод-запуск;
- проверка и обслуживание SSL-сертификатов;
- диагностика типовых сбоев и восстановление.

## 2. Предварительные требования

- Установлены Docker и Docker Compose (`docker compose`).
- Доступны файлы окружения:
  - локально: `.env.dev`;
  - прод: `.env`.
- Для prod SSL:
  - домен указывает на сервер;
  - порты `80/443` открыты;
  - доступна директория `/etc/letsencrypt` на хосте.

## 3. Локальная проверка перед сервером

### 3.1 Подготовка окружения

1. Создать `.env.dev` из шаблона:
  - Linux/macOS: `cp .env.example .env.dev`
  - PowerShell: `Copy-Item .env.example .env.dev`
2. Заполнить минимум:
  - `SECRET_KEY`
  - `POSTGRES_DB`
  - `POSTGRES_USER`
  - `POSTGRES_PASSWORD`
  - `POSTGRES_HOST=db`
  - `POSTGRES_PORT=5432`
  - `DATABASE_URL=postgresql://<user>:<pass>@db:5432/<db>`
  - `TELEGRAM_BOT_TOKEN` (или тестовый токен, если бот не проверяется)
3. Проверить консистентность DB переменных:
  - имя БД в `DATABASE_URL` должно совпадать с `POSTGRES_DB`;
  - если используется удалённая БД, `POSTGRES_HOST` должен указывать
    на внешний хост, а не на `db`;
  - при удалённой БД у роли приложения должны быть права на создание
    таблиц в целевой схеме.

### 3.2 Запуск smoke-теста

- Linux/macOS/Git Bash:
  - `bash scripts/test-local-deploy.sh`

Скрипт автоматически:

- валидирует `docker-compose.local.yml`;
- поднимает стек с `--build`;
- ожидает health статуса сервиса `web`;
- проверяет HTTP endpoints:
  - `http://localhost:8000/health/`
  - `http://localhost:5173/`

### 3.3 Ручная проверка (альтернатива)

1. `docker compose -f docker-compose.local.yml up -d --build`
2. `docker compose -f docker-compose.local.yml ps`
3. `docker compose -f docker-compose.local.yml logs --tail=100 web`
4. Проверить:
  - `http://localhost:8000/health/`
  - `http://localhost:5173/`

## 4. Production запуск

### 4.1 Старт/рестарт

- `docker compose -f docker-compose.prod.yml up -d --build`

### 4.2 Проверка статуса

- `docker compose -f docker-compose.prod.yml ps`
- `docker compose -f docker-compose.prod.yml logs --tail=100 web`
- `docker compose -f docker-compose.prod.yml logs --tail=100 nginx`
- `docker compose -f docker-compose.prod.yml logs --tail=100 certbot`

### 4.3 Health checks

- Backend: `https://<DOMAIN>/health/` (или через внутренний маршрут приложения)
- Контейнеры:
  - `web` должен быть `healthy`;
  - `certbot` должен быть `healthy`.

### 4.4 Поведение scheduler (sync автопарка)

В `docker-compose` scheduler реализован как цикл, который запускает
`python manage.py sync_cars_with_element`, затем делает `sleep`.

- `docker-compose.local.yml`:
  - периодичность: 5 минут (sleep 300 секунд);
  - команда: `sync_cars_with_element`.
- `docker-compose.prod.yml`:
  - периодичность: 60 минут (sleep 3600 секунд);
  - команда: `sync_cars_with_element`.

## 5. SSL: выпуск и автопродление

## 5.1 Текущее поведение

В `docker-compose.prod.yml` настроено:

- сервис `certbot` с циклом `certbot renew` каждые 12 часов;
- скрипт `scripts/check-cert-expiry.sh` до и после renew;
- `healthcheck` certbot через `--healthcheck`;
- сервис `nginx`, который периодически выполняет `reload` для подхвата новых сертификатов.

### 5.2 Ручная проверка сертификата

- `docker compose -f docker-compose.prod.yml exec certbot /bin/sh /app/scripts/check-cert-expiry.sh`

### 5.3 Ручное принудительное обновление

- `docker compose -f docker-compose.prod.yml run --rm certbot certbot renew --webroot -w /var/www/certbot --non-interactive`
- `docker compose -f docker-compose.prod.yml exec nginx nginx -s reload`

## 6. Частые проблемы и решения

### 6.1 `.env.dev not found`

Симптом:

- `docker compose -f docker-compose.local.yml config` падает с ошибкой про `.env.dev`.

Решение:

- создать файл: `Copy-Item .env.example .env.dev`

### 6.2 `web` не становится `healthy`

Проверить:

- `docker compose -f docker-compose.local.yml logs --tail=200 web`
- `docker compose -f docker-compose.local.yml logs --tail=200 db`

Частые причины:

- неверный `DATABASE_URL`;
- `POSTGRES_HOST` не равен `db` в local;
- миграции падают при старте.

### 6.3 Сертификат не обновляется

Проверить:

- `docker compose -f docker-compose.prod.yml logs --tail=200 certbot`
- доступность challenge-пути через nginx:
  - `/.well-known/acme-challenge/`
- наличие volume `/etc/letsencrypt` на хосте.

### 6.4 `permission denied for schema public` при миграциях

Симптом:

- `web` падает на `python manage.py migrate --noinput`;
- в логах ошибка:
  `django.db.utils.ProgrammingError: permission denied for schema public`.

Причина:

- роль БД (например, `refuelbot`) не имеет прав `USAGE/CREATE` на схему
  `public`, хотя TCP-доступ к БД есть.

Решение (выполнять под owner/superuser БД):

- `GRANT CONNECT ON DATABASE <db> TO <user>;`
- `GRANT USAGE, CREATE ON SCHEMA public TO <user>;`
- `GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO <user>;`
- `GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO <user>;`
- при необходимости:
  `ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO <user>;`

Проверка:

- подключиться как `<user>` и выполнить:
  - `CREATE TABLE IF NOT EXISTS public.__perm_test(id int);`
  - `DROP TABLE IF EXISTS public.__perm_test;`

## 7. Безопасное обслуживание

- Перед изменениями в prod сначала прогонять local smoke-test.
- Не выполнять destructive git-команды в runtime на сервере.
- Секреты хранить только в `.env`/`.env.dev` и `local_secrets`, не коммитить.
- После изменения SSL-конфигурации проверять:
  - `docker compose -f docker-compose.prod.yml config`
  - логи `nginx` и `certbot`.

## 8. Полезные команды

### 8.1 Локально

- Поднять: `docker compose -f docker-compose.local.yml up -d --build`
- Остановить: `docker compose -f docker-compose.local.yml down`
- Логи web: `docker compose -f docker-compose.local.yml logs -f web`

### 8.2 Прод

- Поднять: `docker compose -f docker-compose.prod.yml up -d --build`
- Остановить: `docker compose -f docker-compose.prod.yml down`
- Логи certbot: `docker compose -f docker-compose.prod.yml logs -f certbot`
- Логи nginx: `docker compose -f docker-compose.prod.yml logs -f nginx`

## 9. Импорт CSV-дампа (refuel_db)

В проекте есть management-команда:

- `python manage.py import_refuel_dump --path refuel_db`

Команда импортирует данные в порядке зависимостей:

- `regions` -> `users` -> `cars` -> `fuel_records`

Особенности:

- поддерживается валидация ссылочной целостности до записи в БД;
- поле `zone_id` из `users.csv` игнорируется (поле удалено в модели);
- после импорта выполняется синхронизация sequence.

### 9.1 Режим проверки (без записи)

- `python manage.py import_refuel_dump --path refuel_db --dry-run`

Использовать перед реальным импортом, чтобы проверить консистентность CSV.

### 9.2 Боевой импорт

- `python manage.py import_refuel_dump --path refuel_db --truncate`

Где `--truncate` очищает таблицы перед загрузкой.
Если `--truncate` не указан, команда потребует пустые таблицы.

Дополнительно:

- `--batch-size <N>` — размер пачки для `bulk_create` (по умолчанию 1000).

### 9.3 Проверка после импорта

Рекомендуется проверить количество строк:

- `regions` = 6
- `users` = 39
- `cars` = 2798
- `fuel_records` = 11595

И выполнить базовую проверку проекта:

- `python manage.py check`

## 10. Аналитика (раздел «Аналитика» во фронтенде)

Данные отдаёт API `GET /api/v1/analytics/stats` (доступ у ролей с правами
отчётов). Ниже — как интерпретировать блоки дашборда после актуальной логики.

### 10.1 Топливозаправщики в справочнике автомобилей

У модели `Car` есть флаг **`is_fuel_tanker`** («Топливозаправщик»):

- задаётся в админке Django;
- миграция `0015_car_is_fuel_tanker` при применении проставляет флаг
  записям, у которых в поле модели есть подстрока `Caddy` (типичный кейс);
- дальше список корректируется вручную при необходимости.

### 10.2 Первый круговой график: «Распределение по источникам заправки»

Поле ответа: **`refuel_sources`**.

- Учитываются **только** записи со способом **топливная карта** и
  **Telegram-бот** (`source=CARD` и `source=TGBOT`).
- Записи со способом **«Топливозаправщик»** (`TRUCK`) **в этот график не
  входят**.
- Топливозаправщики здесь **не выделяются**: их заправки картой и ботом
  считаются вместе с остальным парком в тех же двух секторах.

### 10.3 Второй блок: «Карта, Telegram-бот и топливозаправщик»

Поле ответа: **`refuel_channels`** (три среза: CARD, TGBOT, TRUCK).

- Во **всех** трёх срезах учитываются **только** заправки на автомобили **без**
  флага топливозаправщика: `car.is_fuel_tanker=False` (записи без привязанного
  автомобиля сюда не попадают).
- **Карта** и **бот** — заправки не-топливозаправщиков соответствующим способом.
- **Топливозаправщик** (`TRUCK`) — выдача топлива с бензовоза **на другие**
  машины (в записи в поле `car` указан получатель, не являющийся
  топливозаправщиком).
- Самозаправ самих топливозаправщиков (карта/бот на `car` с
  `is_fuel_tanker=True`) в этом блоке **не учитывается**.

### 10.4 Топ-20 по сотрудникам и по автомобилям

- **Топ сотрудников** — по убыванию объёма; числа на графиках с группировкой
  разрядов (локаль `ru-RU`).
- **Топ автомобилей по объёму** — **без** машин с `is_fuel_tanker=True`
  (поле **`by_car`**).
- Отдельная карточка **«Топливозаправщики по объёму»** — только машины с
  `is_fuel_tanker=True` (поле **`by_car_fuel_tankers`**).

### 10.5 Docker Compose: переменная `pid` во фронтенд-команде

В `docker-compose.local.yml` / `docker-compose.prod.yml` для shell-команды
фронтенда используется экранирование **`$$`** для переменных shell (`pid=$$!`,
`wait $$pid`), иначе Compose воспринимает `$pid` как подстановку и выдаёт
предупреждение о незаданной переменной `pid`.

### 10.6 Сборка образов: ошибка BuildKit snapshot

При ошибке вида `failed to prepare extraction snapshot` / `parent snapshot ...
does not exist` на Windows с Docker Desktop:

- выполнить `docker builder prune -af`, при необходимости перезапустить Docker
  Desktop;
- при повторении — проверить место на диске и обновить Docker Desktop;
- для диагностики без BuildKit: `DOCKER_BUILDKIT=0 docker compose ... build`.
