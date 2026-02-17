#!/usr/bin/env sh
set -eu

cd /app/src

echo "Running migrations..."
# Retry to handle DB cold start
i=0
until python manage.py migrate --noinput; do
  i=$((i+1))
  if [ "$i" -ge 15 ]; then
    echo "Migrations failed after retries"
    exit 1
  fi
  echo "Migrate failed, retrying in 3s ($i/15)"
  sleep 3
done

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting daphne on port ${PORT:-8080}..."
daphne -b 0.0.0.0 -p "${PORT:-8080}" taskqueue.asgi:application
