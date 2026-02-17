#!/usr/bin/env sh
set -eu

cd /app/src

python manage.py migrate --noinput
python manage.py collectstatic --noinput

daphne -b 0.0.0.0 -p "${PORT:-8000}" taskqueue.asgi:application
