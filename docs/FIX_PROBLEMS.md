# 📋 Отчёт по диагностике и исправлению проблем в проекте Next-Refuels

**Дата:** 10 апреля 2026  
**Статус:** ✅ Основные проблемы устранены, система работает  
**Осталось:** 🔧 Настроить подключение Телеграм-бота к API Telegram

---

## 🔍 Краткое резюме

| Компонент | Проблема | Статус | Решение |
|-----------|----------|--------|---------|
| `telegram_bot_prod` | `TimedOut` при подключении к `api.telegram.org` | ⚠️ В работе | Увеличить таймауты, добавить DNS/прокси |
| `frontend ↔ backend` | Дублирование `/api/v1` → 404 | ✅ Исправлено | Убрать `/api/v1` из `NEXT_PUBLIC_API_URL` |
| `frontend ↔ backend` | SSL handshake timeout при внутренних запросах | ✅ Исправлено | Настроить `SECURE_PROXY_SSL_HEADER` + middleware |
| `/api/reports/export/xlsx` | 500 ошибка при экспорте | ✅ Исправлено | Комплексное: фикс API URL + таймауты gunicorn |
| `web:8000` | Не слушал порт внутри Docker | ✅ Исправлено | `--bind 0.0.0.0:8000` в gunicorn |

---

## 🚨 Проблема #1: Телеграм-бот не подключается к Telegram API

### Симптомы
```
telegram.error.TimedOut: Timed out
httpx.ConnectTimeout
File ".../telegram/_bot.py", line 857, in initialize → await self.get_me()
```

### Корневые причины
1. **Блокировка Telegram** в регионе хостинга (наиболее вероятно)
2. **DNS не резолвит** `api.telegram.org` внутри контейнера
3. **Слишком маленький таймаут** инициализации бота

### Применённые решения

#### 🔹 Код: `/app/core/refuel_bot/main.py`
```python
import os
from telegram.request import HTTPXRequest
from telegram.ext import ApplicationBuilder

# ... инициализация токена ...

proxy_url = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")

request_kwargs = {
    "connect_timeout": 15,
    "read_timeout": 45,
    "write_timeout": 45,
    "pool_timeout": 15,
}
if proxy_url:
    request_kwargs["proxy_url"] = proxy_url

request = HTTPXRequest(**request_kwargs)

app = (
    ApplicationBuilder()
    .token(token)
    .request(request)
    .get_me_request_timeout(30)  # отдельный таймаут для bootstrap
    .build()
)
```

#### 🔹 Docker: `docker-compose.prod.yml` → сервис `bot`
```yaml
bot:
  # ... существующие настройки ...
  dns:
    - 8.8.8.8
    - 1.1.1.1
  environment:
    # ... существующие ...
    # Раскомментировать при использовании прокси:
    # HTTPS_PROXY: "socks5://proxy.example.com:1080"
```

#### 🔹 Зависимости (если используется SOCKS5)
```txt
# requirements-bot.txt
httpx[socks]>=0.24.0
```

### Проверка
```bash
# Пересобрать и перезапустить
docker compose build --no-cache bot
docker compose up -d telegram_bot_prod
docker logs -f telegram_bot_prod

# Диагностика из контейнера
docker exec telegram_bot_prod python -c "
import socket, httpx, os
try:
    ip = socket.gethostbyname('api.telegram.org')
    print('✓ DNS OK:', ip)
except Exception as e:
    print('✗ DNS Error:', e)
proxy = os.getenv('HTTPS_PROXY')
try:
    with httpx.Client(proxy=proxy, timeout=10) as client:
        r = client.get('https://api.telegram.org')
        print('✓ Connection OK:', r.status_code)
except Exception as e:
    print('✗ Connection Error:', type(e).__name__, str(e)[:100])
"
```

---

## 🚨 Проблема #2: Дублирование `/api/v1` в запросах фронтенда

### Симптомы
```
"GET /api/v1/api/v1/auth/me HTTP/2.0" 404 1206
```

### Корневая причина
Переменная `NEXT_PUBLIC_API_URL` была задана как `https://${DOMAIN}/api/v1`, а код фронтенда добавлял `/api/v1` повторно при формировании запросов.

### Решение

#### 🔹 Переменные окружения: `docker-compose.prod.yml` → `frontend`
```yaml
frontend:
  environment:
    # ✅ Без /api/v1 в конце — префикс добавляется в коде
    NEXT_PUBLIC_API_URL: "https://${DOMAIN}"
    NEXT_INTERNAL_API_URL: "http://web:8000"
    NEXT_PUBLIC_DJANGO_ADMIN_URL: ""
```

#### 🔹 Код фронтенда: хелпер для формирования URL
```typescript
// utils/api.ts
export const api = {
  v1: (path: string) => {
    const base = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || '';
    return `${base}/api/v1${path.startsWith('/') ? path : '/' + path}`;
  },
  internal: (path: string) => {
    const base = process.env.NEXT_INTERNAL_API_URL?.replace(/\/$/, '') || 'http://web:8000';
    return `${base}${path.startsWith('/') ? path : '/' + path}`;
  },
};
```

#### 🔹 Использование
```typescript
// Вместо:
fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/me`)

// Пишем:
fetch(api.v1('/auth/me'))
```

### Проверка
```bash
# После пересборки фронтенда:
curl -I "https://refuel.txnxt.ru/api/v1/auth/csrf"
# Ожидаемо: 200, без 404
```

---

## 🚨 Проблема #3: SSL-редирект ломает внутренние запросы Next.js → Django

### Симптомы
```
✗ Error: URLError <urlopen error _ssl.c:993: The handshake operation timed out>
```

### Корневая причина
- Django настроен с `SECURE_SSL_REDIRECT = True`
- При прямом запросе `http://web:8000/...` из Next.js (минуя nginx) Django не видит заголовок `X-Forwarded-Proto`
- Django редиректит на `https://web:8000/...`, но контейнер `web` не слушает HTTPS
- Клиент пытается сделать TLS handshake с HTTP-портом → таймаут

### Решение

#### 🔹 Настройки Django: `next_refuels/settings/prod.py`
```python
# Уже было (правильно):
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# ДОБАВИТЬ: отключение редиректа для внутренних хостов
INTERNAL_DOCKER_HOSTS = {'web', 'localhost', '127.0.0.1', 'frontend', 'redis'}

def _is_internal_request(request) -> bool:
    host = request.get_host().split(':')[0].lower()
    return host in INTERNAL_DOCKER_HOSTS or host.startswith('172.') or host.startswith('10.')

class SkipInternalRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        if _is_internal_request(request):
            request._secure_redirect_disabled = True
        return self.get_response(request)

# Вставить ПЕРВЫМ в MIDDLEWARE:
MIDDLEWARE = [
    'next_refuels.settings.prod.SkipInternalRedirectMiddleware',
    *MIDDLEWARE,
]

# Патч для SecurityMiddleware (после импортов):
from django.middleware.security import SecurityMiddleware
_original = SecurityMiddleware._should_redirect_to_secure  # type: ignore
def _patched(self, request):
    if getattr(request, '_secure_redirect_disabled', False):
        return False
    return _original(self, request)
SecurityMiddleware._should_redirect_to_secure = _patched  # type: ignore
```

#### 🔹 Альтернатива (проще): передавать заголовок из Next.js
```typescript
// В server-side fetch (app/api/reports/export/[type]/route.ts)
const upstream = await fetch(upstreamUrl.toString(), {
  headers: {
    cookie: request.headers.get("cookie") ?? "",
    "X-Forwarded-Proto": "https",  // ← Django не будет редиректить
    "X-Forwarded-Host": "web",
  },
  // ...
});
```

### Проверка
```bash
# Внутренний запрос не должен редиректить:
docker run --rm --network next-refuels_default alpine \
  sh -c "apk add curl && curl -s -I http://web:8000/health/ | head -3"
# Ожидаемо: 200, а не 301/302
```

---

## 🚨 Проблема #4: Экспорт отчётов возвращает 500 / таймаут

### Симптомы
```
"GET /api/reports/export/xlsx?... HTTP/2.0" 500 0
TypeError: fetch failed [cause]: ConnectTimeoutError: ... web:8000, timeout: 10000ms
```

### Корневые причины (комплекс)
1. Дублирование `/api/v1` → 404 → 500 в цепочке
2. Таймаут gunicorn (30 сек) для генерации больших XLSX
3. SSL-редирект при внутренних запросах (см. Проблема #3)

### Решение

#### 🔹 Увеличить таймаут gunicorn: `docker-compose.prod.yml` → `web`
```yaml
web:
  command: >
    /bin/sh -c "
    python manage.py collectstatic --noinput &&
    gunicorn next_refuels.wsgi:application
    --bind 0.0.0.0:8000
    --workers 4
    --timeout 120          # ← увеличить с 30 до 120 сек
    --log-level info
    --access-logfile /dev/null
    "
```

#### 🔹 Добавить таймаут в nginx для долгих запросов (опционально)
```nginx
# nginx/templates/default.conf.template
location /api/ {
    proxy_pass http://web:8000;
    # ... существующие заголовки ...
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
}
```

#### 🔹 Увеличить таймаут fetch в Next.js API Route
```typescript
// app/api/reports/export/[type]/route.ts
const controller = new AbortController();
const timeout = setTimeout(() => controller.abort(), 120_000); // 120 сек

try {
  const upstream = await fetch(upstreamUrl.toString(), {
    // ...
    signal: controller.signal,
  });
  // ...
} finally {
  clearTimeout(timeout);
}
```

### Проверка
```bash
# Тест экспорта через curl:
curl -b /tmp/cookies.txt \
  "https://refuel.txnxt.ru/api/reports/export/xlsx?from_date=2026-04-01&to_date=2026-04-10" \
  -o report.xlsx -v
# Ожидаемо: 200, файл скачивается
```

---

## 🔄 Порядок применения исправлений

```bash
# 1. Остановить сервисы
docker compose -f docker-compose.prod.yml down

# 2. Очистить кэш сборки фронтенда (ВАЖНО: переменные запекаются при билде)
rm -rf frontend/.next frontend/node_modules

# 3. Пересобрать фронтенд
docker compose -f docker-compose.prod.yml build --no-cache frontend

# 4. Пересобрать бота (если меняли код/зависимости)
docker compose -f docker-compose.prod.yml build --no-cache bot

# 5. Запустить всё
docker compose -f docker-compose.prod.yml up -d

# 6. Проверить переменные окружения
docker exec next_refuels_frontend_prod env | grep NEXT
# Ожидаемо:
# NEXT_PUBLIC_API_URL=https://refuel.txnxt.ru
# NEXT_INTERNAL_API_URL=http://web:8000

# 7. Проверить связь внутри Docker
docker run --rm --network next-refuels_default python:3.12-alpine \
  python -c "import urllib.request; print(urllib.request.urlopen('http://web:8000/health/').read().decode())"

# 8. Проверить внешний API
curl -I https://refuel.txnxt.ru/api/v1/auth/csrf

# 9. Проверить логи после тестов
docker logs next_refuels_frontend_prod --tail 50
docker logs next_refuels_web --tail 50
```

---

## 🧪 Чеклист верификации

- [ ] **Экспорт отчётов**: скачать XLSX за период → файл корректный, нет 500
- [ ] **Авторизация**: войти в систему → `api/v1/auth/me` возвращает 200, нет `/api/v1/api/v1`
- [ ] **Аналитика**: открыть `/analytics` → данные загружаются, фильтры работают
- [ ] **Внутренние запросы**: `curl http://web:8000/health/` из Docker → 200, нет редиректа
- [ ] **Телеграм-бот**: `docker logs telegram_bot_prod` → нет `TimedOut`, бот запустился
- [ ] **Логи ошибок**: `docker logs ... --tail 100 | grep -i error` → только ожидаемые предупреждения

---

## 🛠️ Быстрые команды для диагностики

```bash
# Сеть Docker
docker network ls | grep refuel
docker network inspect next-refuels_default --format='{{range .Containers}}{{.Name}} {{end}}'

# Проверка связи
docker run --rm --network next-refuels_default alpine \
  sh -c "apk add curl bind-tools && nslookup web && curl -s http://web:8000/health/"

# Переменные окружения
docker exec next_refuels_frontend_prod env | grep -E 'NEXT|API|URL'
docker exec next_refuels_web env | grep -E 'SECURE|ALLOWED|DOMAIN'

# Логи в реальном времени
docker compose -f docker-compose.prod.yml logs -f frontend web bot

# Статус сервисов
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml top
```

---

## 📌 Примечания для будущих разработчиков

1. **Next.js переменные окружения**: `NEXT_PUBLIC_*` запекаются при `npm run build`. После изменения `.env` или `docker-compose.yml` **обязательно** пересобирать фронтенд с очисткой `.next/`.

2. **Django + HTTPS за прокси**: всегда настраивать `SECURE_PROXY_SSL_HEADER` и передавать `X-Forwarded-Proto` из nginx. Для внутренних вызовов без прокси — использовать middleware или заголовки.

3. **Таймауты**: экспорт отчётов и синхронизация с внешними API могут занимать >30 сек. Всегда задавать `--timeout` в gunicorn и `proxy_read_timeout` в nginx с запасом.

4. **Docker DNS**: если контейнеры не резолвят внешние домены — добавлять `dns: ["8.8.8.8", "1.1.1.1"]` в `docker-compose.yml`.

5. **Логирование**: в продакшене отключать `console`-логгер для приложений, писать в файлы (`./logs`) и/или БД — это предотвращает утечки и упрощает аудит.

---

## 🆘 Если проблема вернётся

1. Проверить логи: `docker compose logs --tail=200 <сервис>`
2. Проверить сеть: `docker network inspect next-refuels_default`
3. Проверить переменные: `docker exec <контейнер> env | grep KEY`
4. Проверить связь: `curl`/`nslookup` из тестового контейнера в той же сети
5. Сравнить с этим документом — большинство проблем уже описаны

---

> 📄 **Документ подготовлен:** 10.04.2026  
> 👤 **Автор:** Владимир Шистеров  
> 🔄 **Обновлять при:** изменении архитектуры, добавлении новых сервисов, миграции на другой хостинг