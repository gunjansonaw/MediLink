# -----------------------------------------------------------
# MediLink Backend - Production Dockerfile (multi-arch: amd64 + arm64)
# -----------------------------------------------------------
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# psycopg2-binary ships wheels for amd64 and arm64, so no compiler is needed
COPY requirements.txt /app/
RUN pip install -r requirements.txt

COPY . /app/

# Static files are baked into the image (served by WhiteNoise)
RUN DEBUG=True SECRET_KEY=build-only DB_ENGINE=django.db.backends.sqlite3 \
    python manage.py collectstatic --noinput \
 && chmod +x /app/entrypoint.sh \
 && useradd --uid 10001 --create-home --shell /usr/sbin/nologin medilink \
 && mkdir -p /app/media \
 && chown -R medilink:medilink /app/media

USER 10001

EXPOSE 8000

# 2 workers x 4 threads; long timeout because AI agent turns can take a while
ENV GUNICORN_CMD_ARGS="--workers 2 --threads 4 --timeout 180 --access-logfile -"

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "medilink.wsgi:application", "--bind", "0.0.0.0:8000"]
