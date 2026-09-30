#!/bin/sh
set -e

echo "==> Waiting for PostgreSQL database to accept connections..."
while ! nc -z "$DB_HOST" "$DB_PORT"; do
  sleep 1
done
echo "==> PostgreSQL is up and running!"

echo "==> Running Django database migrations..."
python manage.py migrate --noinput

echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo "==> Executing application command..."
exec "$@"
