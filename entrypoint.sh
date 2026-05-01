#!/bin/sh
set -e

python manage.py migrate --noinput

exec gunicorn \
    --bind 0.0.0.0:8080 \
    --workers 2 \
    --threads 4 \
    --worker-class gthread \
    --timeout 30 \
    --access-logfile - \
    --error-logfile - \
    movbitsapi.wsgi:application
