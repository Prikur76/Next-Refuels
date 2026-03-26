#!/bin/bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOGFILE="${SCRIPT_DIR}/deploy.log"
COMPOSE="docker compose -f docker-compose.prod.yml"
# Ветка на сервере (по умолчанию main; для master задайте DEPLOY_BRANCH=master).
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"

if [[ ! -f docker-compose.prod.yml ]]; then
    echo "Ошибка: запускайте скрипт из корня репозитория (нет docker-compose.prod.yml)." \
        | tee -a "$LOGFILE"
    exit 1
fi

# Загрузка .env в текущую оболочку (без «export $(grep…)» — безопаснее для пробелов).
if [[ -f .env ]]; then
    set +u
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
    set -u
else
    echo "Предупреждение: файл .env не найден, полагаемся на env окружения." \
        | tee -a "$LOGFILE"
fi

if [[ -z "${DOMAIN:-}" || -z "${LETSENCRYPT_EMAIL:-}" ]]; then
    echo "❌ В .env (или окружении) задайте DOMAIN и LETSENCRYPT_EMAIL." \
        | tee -a "$LOGFILE"
    exit 1
fi

echo "=====================================================" | tee -a "$LOGFILE"
echo " 🚀 Starting Deployment for ${DOMAIN}" | tee -a "$LOGFILE"
echo "=====================================================" | tee -a "$LOGFILE"

############################################
# ROLLBACK
############################################
rollback() {
    # Иначе сбой внутри rollback снова вызовет ERR и зациклит вывод.
    trap - ERR
    echo ""
    echo "❗ ERROR: Deployment failed! Rolling back..." | tee -a "$LOGFILE"
    echo "Stopping containers..." | tee -a "$LOGFILE"
    # Без -v: не удалять тома (static, media, redis и т.д.) — см. SPEC P0.
    $COMPOSE down || true
    echo "Resetting code..." | tee -a "$LOGFILE"
    git reset --hard HEAD~1 || true
    echo "✔ Rollback complete." | tee -a "$LOGFILE"
    exit 1
}
trap rollback ERR

############################################
# UPDATE CODE
############################################
echo "🔄 Pulling latest code..." | tee -a "$LOGFILE"
git fetch origin
git reset --hard "origin/${DEPLOY_BRANCH}"

############################################
# BUILD IMAGES
############################################
echo ""
echo "🛠 Building Docker images..." | tee -a "$LOGFILE"
$COMPOSE build

############################################
# START SERVICES
############################################
echo ""
echo "🚀 Starting containers..." | tee -a "$LOGFILE"
$COMPOSE up -d

############################################
# WAIT FOR WEB TO BE HEALTHY
############################################
echo ""
echo "⏳ Waiting for web to become healthy..." | tee -a "$LOGFILE"

CONTAINER_ID=$($COMPOSE ps -q web || true)
if [[ -z "$CONTAINER_ID" ]]; then
    echo "❌ Cannot find container id for service 'web'" | tee -a "$LOGFILE"
    $COMPOSE ps | tee -a "$LOGFILE"
    exit 1
fi

STATUS=""
for i in {1..30}; do
    STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_ID" 2>/dev/null || echo "unknown")
    echo "Check $i: web health status = $STATUS" | tee -a "$LOGFILE"
    if [[ "$STATUS" == "healthy" ]]; then
        echo "✔ Web is healthy!" | tee -a "$LOGFILE"
        break
    fi
    sleep 2
done

if [[ "$STATUS" != "healthy" ]]; then
    echo "❌ Web failed to become healthy (status=$STATUS)" | tee -a "$LOGFILE"
    docker inspect "$CONTAINER_ID" | tee -a "$LOGFILE"
    echo "Attempting HTTP /health check via nginx..." | tee -a "$LOGFILE"
    $COMPOSE exec -T --index 1 nginx sh -c 'curl -sS -I http://web:8000/health/ || true' | tee -a "$LOGFILE"
    exit 1
fi

############################################
# CHECK DATABASE CONNECTION
############################################
echo ""
echo "🗄 Checking Postgres database connection..." | tee -a "$LOGFILE"

MAX_TRIES=10
SLEEP_SEC=5
DB_OK=0

for i in $(seq 1 $MAX_TRIES); do
    echo "Check $i: Testing DB connection..." | tee -a "$LOGFILE"

    $COMPOSE exec -T web python -c "
import sys, psycopg2, os
try:
    conn = psycopg2.connect(
        dbname=os.environ.get('POSTGRES_DB'),
        user=os.environ.get('POSTGRES_USER'),
        password=os.environ.get('POSTGRES_PASSWORD'),
        host=os.environ.get('POSTGRES_HOST'),
        port=int(os.environ.get('POSTGRES_PORT', 5432))
    )
    conn.close()
except Exception:
    sys.exit(1)
" && DB_OK=1 && break

    echo "⚠ DB not reachable yet, waiting $SLEEP_SEC sec..." | tee -a "$LOGFILE"
    sleep $SLEEP_SEC
done

if [[ "$DB_OK" != "1" ]]; then
    echo "❌ Cannot connect to Postgres database after $MAX_TRIES attempts." \
        | tee -a "$LOGFILE"
    exit 1
fi

echo "✔ Database connection OK!" | tee -a "$LOGFILE"

############################################
# APPLY MIGRATIONS
############################################
echo ""
echo "🗄 Applying migrations..." | tee -a "$LOGFILE"
$COMPOSE exec -T web python manage.py migrate --noinput

############################################
# CREATE SUPERUSER
############################################
echo ""
echo "👤 Creating superuser (if needed)..." | tee -a "$LOGFILE"
$COMPOSE exec -T web python manage.py create_superuser || true

############################################
# COLLECT STATIC FILES
############################################
echo ""
echo "📦 Collecting static files..." | tee -a "$LOGFILE"
$COMPOSE exec -T web python manage.py collectstatic --noinput

############################################
# CLEANUP
############################################
echo ""
echo "🧹 Cleaning unused docker resources..." | tee -a "$LOGFILE"
docker system prune -f >/dev/null 2>&1 || true

############################################
# CHECK MAIN SERVICES
############################################
echo ""
echo "🏃 Checking running services..." | tee -a "$LOGFILE"
required=(
    "next_refuels_web"
    "next_refuels_nginx"
    "next_refuels_frontend_prod"
    "next_refuels_redis_prod"
    "next_refuels_certbot"
    "telegram_bot_prod"
    "scheduler_prod"
)

for svc in "${required[@]}"; do
    if docker ps --format '{{.Names}}' | grep -q "^${svc}$"; then
        echo "✔ $svc is running" | tee -a "$LOGFILE"
    else
        echo "❌ $svc is NOT running!" | tee -a "$LOGFILE"
        exit 1
    fi
done

############################################
# SSL CERTIFICATES
############################################
echo ""
echo "🔐 Checking / obtaining SSL certificates..." | tee -a "$LOGFILE"

CERT_PATH="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"

if [ ! -f "$CERT_PATH" ]; then
    echo "⚠ Certificate not found. Issuing a new one via certbot..." | tee -a "$LOGFILE"
    $COMPOSE run --rm certbot certonly \
        --webroot \
        -w /var/www/certbot \
        -d "$DOMAIN" \
        --email "$LETSENCRYPT_EMAIL" \
        --agree-tos \
        --no-eff-email || {
            echo "❌ Failed to obtain SSL certificate!" | tee -a "$LOGFILE"
            exit 1
        }
else
    echo "✔ Certificate exists. Attempting renewal..." | tee -a "$LOGFILE"
    $COMPOSE run --rm certbot renew --webroot -w /var/www/certbot --non-interactive || \
        echo "⚠ SSL renewal failed or rate-limited, continuing..." | tee -a "$LOGFILE"
fi

############################################
# RELOAD NGINX
############################################
echo ""
echo "🔄 Reloading nginx to apply certs..." | tee -a "$LOGFILE"
$COMPOSE exec -T nginx nginx -s reload

############################################
# DONE
############################################
trap - ERR
echo ""
echo "=====================================================" | tee -a "$LOGFILE"
echo " ✨ Deployment complete!" | tee -a "$LOGFILE"
echo "=====================================================" | tee -a "$LOGFILE"
