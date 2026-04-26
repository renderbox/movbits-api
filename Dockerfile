FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    "django>=6.0.4,<7.0" \
    "django-allauth>=65.7.0,<66.0.0" \
    "pillow>=11.2.1,<12.0.0" \
    "gunicorn" \
    "psycopg2-binary" \
    "dj-database-url" \
    "boto3" \
    "cryptography>=43.0.0" \
    "django-storages[s3]>=1.14.6,<2.0.0" \
    "python-dotenv>=1.1.0,<2.0.0" \
    "whitenoise>=6.9.0,<7.0.0" \
    "redis>=6.2.0,<7.0.0" \
    "stripe>=12.2.0,<13.0.0" \
    "django-anymail>=13.0,<14.0" \
    "django-cors-headers>=4.7.0,<5.0.0" \
    "djangorestframework>=3.16.0,<4.0.0" \
    "djangorestframework-simplejwt>=5.5.0,<6.0.0" \
    "dj-rest-auth>=7.0.0,<8.0.0" \
    "drf-spectacular[sidecar]>=0.28.0,<0.29.0" \
    "django-vendor>=0.7.0,<0.8.0" \
    "django-site-configs>=0.4.0,<0.5.0" \
    "django-integrations>=0.4.0,<0.5.0" \
    "python-json-logger>=4.0.0,<5.0.0" \
    "google-cloud-pubsub>=2.26.0,<3.0.0" \
    "google-cloud-bigquery>=3.0.0,<4.0.0" \
    "django-invitations>=2.0.0,<3.0.0"

COPY src/ ./src/
COPY manage.py ./

RUN DJANGO_SETTINGS_MODULE=movbitsapi.settings.prod \
    DATABASE_URL=sqlite:////tmp/build.db \
    python manage.py collectstatic --noinput

EXPOSE 8080

CMD exec gunicorn \
    --bind 0.0.0.0:8080 \
    --workers 2 \
    --threads 4 \
    --worker-class gthread \
    --timeout 30 \
    --access-logfile - \
    --error-logfile - \
    movbitsapi.wsgi:application
