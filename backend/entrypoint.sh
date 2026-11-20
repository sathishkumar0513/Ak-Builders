#!/bin/sh
set -e

if [ -n "$DATABASE_URL" ]; then
  # Hosted database (Neon): it may be waking from sleep, so let migrate retry a few times
  echo "Using DATABASE_URL"
else
  echo "Waiting for PostgreSQL at $DB_HOST:$DB_PORT ..."
  until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" >/dev/null 2>&1; do
    sleep 1
  done
fi

n=0
until python manage.py migrate --noinput; do
  n=$((n+1)); [ "$n" -ge 5 ] && exit 1
  echo "migrate failed, retrying in 5s ($n/5)"; sleep 5
done
python manage.py collectstatic --noinput
if [ "${SEED_ON_START:-False}" = "True" ]; then
  python manage.py seed_data
fi

exec "$@"
