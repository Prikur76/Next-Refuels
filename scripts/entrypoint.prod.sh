#!/bin/sh
set -e

echo "⏳ Waiting for PostgreSQL..."
python scripts/wait-for-db.py

# Если переданы аргументы (например, command из docker-compose) — выполнить их
if [ "$#" -gt 0 ]; then
    echo "🎯 Running custom command: $*"
    exec "$@"
fi

# Иначе — запустить веб-сервер
echo "🚀 Starting Gunicorn..."
exec gunicorn next_refuels.asgi:application \
    -k uvicorn.workers.UvicornWorker \
    --workers 4 \
    --bind 0.0.0.0:8000 \
    --log-level info
