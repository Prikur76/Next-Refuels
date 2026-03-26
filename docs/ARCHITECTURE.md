# Next-Refuels — архитектура

## Обзор

`Next-Refuels` — корпоративная система учёта заправок автопарка. Платформа
состоит из:

- веб-приложения на Django (ввод заправок, отчеты, админка);
- Telegram-бота для оперативного ввода заправок;
- фонового scheduler (синхронизация автопарка из `1C:Элемент`);

Архитектура построена вокруг единых доменных сущностей и сервисного слоя
(`core/services`), чтобы одинаковая бизнес-логика применялась и в вебе, и
в боте.

## Границы системы (C4 - упрощенно)

### Контекст

```mermaid
flowchart LR
  U["Пользователь"] --> W["Веб-интерфейс Django"]
  U --> T["Telegram-бот"]
  W --> API["Django backend: Ninja API + views"]
  T --> API
  API --> DB["PostgreSQL"]
  API --> Cache["Redis cache"]
  API --> S1C["1C:Элемент API"]
  Scheduler["Scheduler container"] --> API
  API --> Logs["SystemLog + лог-файлы"]
```

### Компоненты

- `frontend/` — веб-клиент на Next.js для ввода и аналитики.
- `next_refuels/` — Django project (settings, URLs, ASGI).
- `core/` - доменные сущности, представления и сервисы:
  - `models/`: `User`, `Car`, `Region`, `FuelRecord`, `SystemLog`;
  - `views.py`: веб-страницы (`/`, `/fuel/add/`, `/fuel/reports/`, ...);
  - `api.py`: HTTP API контур через `django-ninja`;
  - `refuel_bot/`: Telegram диалоги и middleware доступа;
  - `clients/`: клиенты внешних API (`element_car_client.py`);
  - `services/`: бизнес-логика и интеграции (например, `fuel_service`).
  - `management/commands/`: команды синхронизации.
- `docker-compose*.yml`:
  - `web`: backend;
  - `bot`: Telegram bot;
  - `scheduler`: периодический запуск синка автопарка;
  - `nginx/templates/`: reverse proxy и SSL (prod), подстановка `DOMAIN` при старте.

## Основные сценарии и потоки данных

### 1. Ввод заправки через веб

1. Пользователь открывает `/fuel/add/`.
2. Django view получает `car`, `liters`, `source` и формирует payload.
3. `FuelService.normalize_liters` валидирует и нормализует объем.
4. `FuelService.create_fuel_record`:
   - проверяет, что `Car` активна;
   - создает `FuelRecord` в БД.
5. Запись доступна в отчетах (`/fuel/reports/` и API `/reports/*`).

### 2. Ввод заправки через Telegram

1. `ConversationHandler` ведет пошаговый диалог (госномер -> литры -> способ).
2. `core/refuel_bot/middleware/access_middleware.py`:
   - связывает Telegram user с `core.User` по одноразовому коду из `/start`
     или `/link`;
   - проверяет наличие активного пользователя и групп доступа;
   - кэширует профиль на 15 минут (ключ `bot_user:<telegram_id>`).
3. После успешного ввода вызывается `FuelService.create_fuel_record`.
4. Созданная запись доступна в отчетах.

### 3. Синхронизация автомобилей из `1C:Элемент`

1. Scheduler запускает `python manage.py sync_cars_with_element`.
2. Команда использует `ElementCarClient.sync_with_database()`:
   - получает данные с внешнего API;
   - маппит внешние сущности в внутренние `Region`/`Car`;
   - архивирует отсутствующие автомобили (если настроено в логике клиента);
   - пишет итоги синхронизации в `SystemLog`.
3. Ошибки синхронизации логируются и не “роняют” контейнер (в зависимости
   от сценария запуска).

## Доменные сущности (ключевые поля)

- `User`: пользователь Django, содержит `telegram_id` и FK на `Region`.
- `Car`: автомобиль компании, связан с `Region` и помечается активным/архивным.
- `FuelRecord`: факт заправки, содержит объем, топливо, источник, статус
  подтверждения и ссылки на `Car` и сотрудника (`User`).
- `SystemLog`: аудит пользовательских и системных событий.

## Наблюдаемость

- Health endpoint backend: `/health/` (используется Docker healthcheck).
- Логирование:
  - `SystemLog` (структурированный аудит);
  - общий log-файл через Django logging конфиг.

