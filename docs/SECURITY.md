# Next-Refuels — безопасность

## Модель угроз (кратко)

Основные риски для системы учета заправок:

- несанкционированный ввод/изменение заправок и доступ к отчетам;
- перебор учетных данных (password guessing / auth abuse);
- CSRF для веб-сценариев, где используется cookie-based auth;
- ошибки авторизации Telegram-бота (в т.ч. привязка Telegram к аккаунту);
- утечка секретов (ключи, токены, credential JSON для интеграций).

## Контроль доступа (AuthN/AuthZ)

### AuthN: сессии, cookie и CSRF

- Django использует `SessionMiddleware` и cookie-based сессии.
- Настройки cookie и CSRF:
  - `SESSION_COOKIE_HTTPONLY = True`;
  - `SESSION_COOKIE_SAMESITE = Lax`;
  - `CSRF_COOKIE_SAMESITE = Lax`;
  - доверенные origin-ы для CSRF задаются через
    `CSRF_TRUSTED_ORIGINS` (dev: `http://localhost:5173` и
    `http://localhost:8000`).
- Для фронтенда (Next.js) предусмотрен endpoint:
  - `GET /api/v1/auth/csrf` (выставляет CSRF cookie через `ensure_csrf_cookie`).

### Rate limiting / throttling логина

Для защиты от перебора реализован middleware `core.middleware.auth_throttle`:

- `AUTH_THROTTLE_ENABLED` (по умолчанию `True`);
- `AUTH_THROTTLE_LIMIT`;
- `AUTH_THROTTLE_WINDOW_SECONDS`;
- `AUTH_THROTTLE_LOCK_SECONDS`.

Эти параметры настраиваются через env и применяются к попыткам входа.

### MFA / Identity provider (readiness)

В настройках присутствуют:

- `AUTH_PROVIDER` (по умолчанию `local`);
- `MFA_POLICY_ENABLED` (по умолчанию `False`);
- поля для SSO (`SSO_METADATA_URL`, `SSO_CLIENT_ID`, `SSO_CLIENT_SECRET`).

Документация фиксирует готовность к SSO/MFA, но фактическая политика
включается через конфигурацию.

### AuthZ: RBAC по группам

В системе используются группы Django и проверки на уровне:

- веба: `FuelService.ensure_input_access(...)` и
  `FuelService.ensure_reports_access(...)`;
- API: те же проверки через `FuelService` (в `core/api.py`);
- Telegram: middleware доступа `core/refuel_bot/middleware/access_middleware.py`.

Роли:

- `Заправщик` - ввод заправок;
- `Менеджер` - ввод заправок и просмотр отчетов;
- `Администратор` - полный доступ и аудит.

Для Telegram используется проверка групп:

- доступны пользователи с `Заправщик|Менеджер|Администратор`.

## Валидация входных данных

- В API используется `ninja.Schema` с регулярными ограничениями:
  - `fuel_type` паттерн `^(GASOLINE|DIESEL)$`;
  - `source` паттерн `^(CARD|TGBOT|TRUCK)$`.
- Объем заправки валидируется в `FuelService.normalize_liters`:
  - нормализация разделителя `,` -> `.`;
  - проверка диапазона и корректного формата.
- На уровне доменной модели есть check constraint для положительного объема.
- Авто проверяется на существование и активность:
  - `Car.objects.get(..., is_active=True)`.

## Секреты и конфигурация

- Секреты должны храниться в `.env`/`.env.dev` и директории `local_secrets`.
- `local_secrets/` исключен из коммита через `.gitignore`.
- В прод-сценарии контейнеру `web`/`bot` монтируется `./local_secrets`
  с опцией `:ro` (read-only).

## Аудит и наблюдаемость (security-relevant)

- Структурированный аудит событий ведется в `core.models.SystemLog`.
- Для логирования используется `core/utils/logging.py`:
  - `log_action(...)` для пользовательских действий;
  - `log_access_event(...)` для событий доступа;
  - команды синхронизаций логируют успех/ошибки в SystemLog.
- Health endpoint: `/health/` (полезно для диагностики отказов).

## Сетевые ограничения

- `ALLOWED_HOSTS` зависит от `DEBUG`:
  - в dev по умолчанию разрешены только `127.0.0.1` и `localhost`;
  - в докере/контейнерной среде это важно, т.к. host может быть
    `web:8000`, что приведет к `DisallowedHost`.

Если фронтенд ходит к backend из docker-сети, убедитесь, что:

- `DEBUG` выставлен корректно, и
- `ALLOWED_HOSTS` дополнен нужными host-именами.

## Известные пробелы baseline (что стоит улучшить)

- MFA по умолчанию отключен (`MFA_POLICY_ENABLED = False`).
- Деталей по политике password complexity/lockout на уровне login не
  фиксируется в документации; актуальность зависит от реализации
  `AuthThrottleMiddleware` и настроек env.

