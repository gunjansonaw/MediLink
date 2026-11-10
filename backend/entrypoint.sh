#!/bin/sh
set -e

# Works with either DATABASE_URL or DB_HOST/DB_PORT (the old nc-based loop hung
# forever when only DATABASE_URL was set).
echo "==> Waiting for the database..."
python manage.py wait_for_db --timeout "${DB_WAIT_TIMEOUT:-90}"

# In Kubernetes migrations run in an initContainer, so app pods set RUN_MIGRATIONS=0.
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "==> Running Django database migrations..."
  python manage.py migrate --noinput
fi

if [ "${SEED_DEMO_DATA:-0}" = "1" ]; then
  echo "==> Seeding demo data (idempotent)..."
  python manage.py seed_demo_data
fi

echo "==> Executing application command..."
exec "$@"
