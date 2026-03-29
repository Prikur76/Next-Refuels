#!/bin/sh
set -e

echo "⏳ Waiting for PostgreSQL..."
python scripts/wait-for-db.py

echo "🔄 Running migrations..."
python manage.py migrate --noinput

echo "🔐 Creating superuser..."
python manage.py create_superuser

echo "📦 Collecting static (dev)..."
python manage.py collectstatic --noinput

if [ "$#" -gt 0 ]; then
    echo "🎯 Running custom command: $*"
    exec "$@"
fi

echo "🚀 Starting Uvicorn with hot reload..."
exec uvicorn next_refuels.asgi:application \
    --host 0.0.0.0 \
    --port 8000 \
    --reload
