#!/bin/bash
set -e

echo "Waiting for PostgreSQL..."
while ! nc -z db 5432; do sleep 0.1; done

echo "Waiting for Redis..."
while ! nc -z redis 6379; do sleep 0.1; done

if [ "$RUN_MIGRATIONS" = "true" ]; then
    python src/manage.py migrate --noinput
fi

if [ "$DJANGO_ENV" = "production" ]; then
    python src/manage.py collectstatic --noinput
fi

exec "$@"
