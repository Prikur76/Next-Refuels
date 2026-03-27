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
  - шаблоны:
    - `/.env.example` — расширенный dev/local шаблон;
    - `/.env.prod.example` — минимальный production шаблон.
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

Перед первым запуском:

1. Создать `.env` из prod-шаблона:
  - `cp .env.prod.example .env`
2. Заполнить минимум:
  - `SECRET_KEY`, `DOMAIN`, `LETSENCRYPT_EMAIL`;
  - `ALLOWED_HOSTS`, `EXTRA_ALLOWED_HOSTS`;
  - `DATABASE_URL` и `POSTGRES_*`;
  - `TELEGRAM_BOT_TOKEN` (если включён сервис `bot`);
  - `ELEMENT_API_*` (если используется sync с `1C:Элемент`).

Примечание по host-настройкам в prod:

- `docker-compose.prod.yml` задаёт `ALLOWED_HOSTS` как
  `${DOMAIN},localhost,127.0.0.1,web`;
- дополнительные внешние host (например apex-домен и IP для прямой проверки)
  задавайте через `EXTRA_ALLOWED_HOSTS`.

Минимальная матрица переменных:

| Переменная/блок | Статус | Когда обязательна |
|---|---|---|
| `SECRET_KEY`, `DEBUG=False`, `DOMAIN`, `LETSENCRYPT_EMAIL` | обязательно | всегда в prod |
| `ALLOWED_HOSTS`, `EXTRA_ALLOWED_HOSTS` | обязательно | всегда в prod |
| `DATABASE_URL`, `POSTGRES_*` | обязательно | всегда в prod |
| `TELEGRAM_*` | условно | если запускается `bot` |
| `ELEMENT_API_*` | условно | если используется `sync_cars_with_element` |
| `SSO_*`, `MFA_POLICY_ENABLED` | опционально | только при включении SSO/MFA |
| `EMAIL_*` | опционально | если нужны email-уведомления |

### 4.1 Старт/рестарт

- `docker compose -f docker-compose.prod.yml up -d --build`

### 4.2 Проверка статуса

- `docker compose -f docker-compose.prod.yml ps`
- `docker compose -f docker-compose.prod.yml logs --tail=100 web`
- `docker compose -f docker-compose.prod.yml logs --tail=100 nginx`
- `docker compose -f docker-compose.prod.yml logs --tail=100 certbot`

### 4.3 Health checks

- Nginx: `https://<DOMAIN>/healthz` (проверка, что reverse-proxy отвечает)
- Backend (Django): `https://<DOMAIN>/health/` (проверка приложения)
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

### 5.1 Текущее поведение

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

### 6.5 `PermissionError: /app/logs/errors.log` в web-контейнере

Симптом:

- `web` уходит в `Restarting` / `unhealthy`;
- в логах `next_refuels_web` ошибка:
  `PermissionError: [Errno 13] Permission denied: '/app/logs/errors.log'`.

Причина:

- `./logs` смонтирован как bind-mount (`./logs:/app/logs`);
- директория на хосте принадлежит `root:root` и недоступна на запись
  пользователю контейнера (`uid=1000`, `appuser`).

Решение:

- `cd /opt/next-refuels`
- `mkdir -p logs local_secrets`
- `sudo chown -R 1000:1000 logs local_secrets`
- `sudo chmod -R u+rwX logs local_secrets`
- `docker compose -f docker-compose.prod.yml up -d`
- `docker compose -f docker-compose.prod.yml ps`
- `docker compose -f docker-compose.prod.yml logs --tail=100 web`

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

## 9. CI/CD для одного VPS (GitHub Actions)

### 9.1 Быстрый чеклист первичной настройки VPS

1. Подготовить сервер:
  - установить Docker Engine и Docker Compose plugin;
  - открыть входящие `22/tcp`, `80/tcp`, `443/tcp`;
  - настроить DNS `A`-запись домена на IP сервера.
2. Создать пользователя деплоя (без root):
  - пример: `deploy`;
  - добавить в группу `docker`, чтобы можно было выполнять
    `docker compose` без `sudo`.
3. Развернуть проект на сервере:
  - создать каталог, например `/opt/next-refuels`;
  - выполнить первый `git clone` репозитория в этот каталог.
4. Подготовить секреты и окружение:
  - создать `.env` в каталоге проекта;
  - проверить обязательные переменные (`DOMAIN`, `SECRET_KEY`,
    DB/Redis/Telegram и т.д.);
  - убедиться, что `.env` не попадает в git.
5. Подготовить bind-mount директории с правами для контейнеров:
  - `cd /opt/next-refuels`
  - `mkdir -p logs local_secrets`
  - `sudo chown -R 1000:1000 logs local_secrets`
  - `sudo chmod -R u+rwX logs local_secrets`
6. Проверить базовый прод-старт вручную:
  - `docker compose -f docker-compose.prod.yml up -d --build`;
  - `docker compose -f docker-compose.prod.yml ps`;
  - `https://<DOMAIN>/healthz` возвращает `200 OK` (nginx);
  - `https://<DOMAIN>/health/` возвращает `200 OK` (backend).
7. Настроить GitHub Secrets:
  - `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, `VPS_PORT`, `VPS_APP_PATH`.
8. Запустить GitHub workflow `Deploy to VPS` вручную один раз
   (`workflow_dispatch`) и проверить, что деплой проходит end-to-end.

### 9.2 Экспресс-верификация после каждого деплоя

- `docker compose -f docker-compose.prod.yml ps`:
  - `web` и `certbot` в статусе `healthy`.
- Проверить endpoint:
  - `curl -I https://<DOMAIN>/healthz`
  - `curl -I https://<DOMAIN>/health/`
- Проверить UI и ключевой flow:
  - логин;
  - ввод заправки;
  - просмотр отчета.
- Если есть инцидент:
  - `docker compose -f docker-compose.prod.yml logs --tail=200 web`
  - `docker compose -f docker-compose.prod.yml logs --tail=200 nginx`
  - `docker compose -f docker-compose.prod.yml logs --tail=200 certbot`

### 9.3 Команды для первичной настройки Ubuntu VPS

1. Обновить систему и поставить базовые пакеты:
  - `sudo apt update && sudo apt -y upgrade`
  - `sudo apt -y install ca-certificates curl git ufw fail2ban`
2. Установить Docker + Compose plugin:
  - `sudo install -m 0755 -d /etc/apt/keyrings`
  - `curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg`
  - `sudo chmod a+r /etc/apt/keyrings/docker.gpg`
  - `echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null`
  - `sudo apt update`
  - `sudo apt -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin`
  - `sudo systemctl enable --now docker`
3. Создать пользователя деплоя и выдать доступ к Docker:
  - `sudo adduser --disabled-password --gecos "" deploy`
  - `sudo usermod -aG sudo deploy`
  - `sudo usermod -aG docker deploy`
4. Настроить firewall:
  - `sudo ufw default deny incoming`
  - `sudo ufw default allow outgoing`
  - `sudo ufw allow OpenSSH`
  - `sudo ufw allow 80/tcp`
  - `sudo ufw allow 443/tcp`
  - `sudo ufw --force enable`
5. Подготовить каталог проекта:
  - `sudo mkdir -p /opt/next-refuels`
  - `sudo chown -R deploy:deploy /opt/next-refuels`
  - `sudo -u deploy -H bash -lc 'cd /opt/next-refuels && git clone <REPO_URL> .'`
6. Создать `.env` на сервере:
  - `sudo -u deploy -H bash -lc 'cd /opt/next-refuels && cp .env.example .env'`
  - `sudo -u deploy -H bash -lc 'cd /opt/next-refuels && nano .env'`
7. Подготовить bind-mount директории:
  - `sudo -u deploy -H bash -lc 'cd /opt/next-refuels && mkdir -p logs local_secrets'`
  - `sudo chown -R 1000:1000 /opt/next-refuels/logs /opt/next-refuels/local_secrets`
  - `sudo chmod -R u+rwX /opt/next-refuels/logs /opt/next-refuels/local_secrets`

### 9.4 One-shot script для чистого Ubuntu

Скрипт ниже автоматизирует шаги 9.3 (кроме `git clone` и заполнения `.env`).
Запускать под `root`:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_USER="${DEPLOY_USER:-deploy}"
APP_DIR="${APP_DIR:-/opt/next-refuels}"

apt update && apt -y upgrade
apt -y install ca-certificates curl git ufw fail2ban gnupg

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu \
$(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list

apt update
apt -y install docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker

if ! id -u "$DEPLOY_USER" >/dev/null 2>&1; then
  adduser --disabled-password --gecos "" "$DEPLOY_USER"
fi

usermod -aG sudo "$DEPLOY_USER"
usermod -aG docker "$DEPLOY_USER"

mkdir -p "$APP_DIR"
chown -R "$DEPLOY_USER:$DEPLOY_USER" "$APP_DIR"

ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "Done. Next:"
echo "1) add SSH key for user $DEPLOY_USER"
echo "2) git clone repo into $APP_DIR"
echo "3) create and fill $APP_DIR/.env"
```

### 9.5 Привязка SSH-ключа GitHub Actions (end-to-end)

1. Сгенерировать отдельный deploy-ключ локально:
  - `ssh-keygen -t ed25519 -f ./gha_deploy_ed25519 -C "gha-deploy"`
2. Добавить публичный ключ на VPS для пользователя `deploy`:
  - `sudo -u deploy mkdir -p /home/deploy/.ssh`
  - `sudo -u deploy chmod 700 /home/deploy/.ssh`
  - `sudo -u deploy touch /home/deploy/.ssh/authorized_keys`
  - `sudo -u deploy chmod 600 /home/deploy/.ssh/authorized_keys`
  - `echo "<CONTENTS_OF_gha_deploy_ed25519.pub>" | sudo tee -a /home/deploy/.ssh/authorized_keys > /dev/null`
3. Проверить права:
  - `sudo chown -R deploy:deploy /home/deploy/.ssh`
  - `sudo ls -la /home/deploy/.ssh`
4. Добавить приватный ключ в GitHub:
  - Repo -> `Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`;
  - имя секрета: `VPS_SSH_KEY`;
  - значение: содержимое файла `gha_deploy_ed25519`.
5. Добавить остальные секреты для workflow деплоя:
  - `VPS_HOST`, `VPS_USER`, `VPS_PORT`, `VPS_APP_PATH`.
6. Проверить подключение с локальной машины до запуска CI:
  - `ssh -i ./gha_deploy_ed25519 deploy@<VPS_HOST> "echo ok"`
7. Запустить workflow `Deploy to VPS` вручную (`workflow_dispatch`) и убедиться,
   что шаг `Deploy over SSH` проходит без ошибок.

## 10. Импорт CSV-дампа (refuel_db)

В проекте есть management-команда:

- `python manage.py import_refuel_dump --path refuel_db`

Команда импортирует данные в порядке зависимостей:

- `regions` -> `users` -> `cars` -> `fuel_records`

Особенности:

- поддерживается валидация ссылочной целостности до записи в БД;
- поле `zone_id` из `users.csv` игнорируется (поле удалено в модели);
- после импорта выполняется синхронизация sequence.

### 10.1 Режим проверки (без записи)

- `python manage.py import_refuel_dump --path refuel_db --dry-run`

Использовать перед реальным импортом, чтобы проверить консистентность CSV.

### 10.2 Боевой импорт

- `python manage.py import_refuel_dump --path refuel_db --truncate`

Где `--truncate` очищает таблицы перед загрузкой.
Если `--truncate` не указан, команда потребует пустые таблицы.

Дополнительно:

- `--batch-size <N>` — размер пачки для `bulk_create` (по умолчанию 1000).

### 10.3 Проверка после импорта

Рекомендуется проверить количество строк:

- `regions` = 6
- `users` = 39
- `cars` = 2798
- `fuel_records` = 11595

И выполнить базовую проверку проекта:

- `python manage.py check`

## 11. Технические заметки

### 11.1 Docker Compose: переменная `pid` во фронтенд-команде

В `docker-compose.local.yml` / `docker-compose.prod.yml` для shell-команды
фронтенда используется экранирование **`$$`** для переменных shell (`pid=$$!`,
`wait $$pid`), иначе Compose воспринимает `$pid` как подстановку и выдаёт
предупреждение о незаданной переменной `pid`.

### 11.2 Сборка образов: ошибка BuildKit snapshot

При ошибке вида `failed to prepare extraction snapshot` / `parent snapshot ...
does not exist` на Windows с Docker Desktop:

- выполнить `docker builder prune -af`, при необходимости перезапустить Docker
  Desktop;
- при повторении — проверить место на диске и обновить Docker Desktop;
- для диагностики без BuildKit: `DOCKER_BUILDKIT=0 docker compose ... build`.
