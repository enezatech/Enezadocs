#!/bin/sh
set -e

python manage.py migrate --noinput
python manage.py ensure_superuser
python manage.py collectstatic --noinput

exec uvicorn config.asgi:application \
    --host 0.0.0.0 \
    --port "${UVICORN_PORT:-8000}" \
    --workers "${UVICORN_WORKERS:-3}"
