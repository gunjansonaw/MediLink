# -----------------------------------------------------------
# MediLink Backend - Production Dockerfile
# Python 3.11 Slim
# -----------------------------------------------------------
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    netcat-traditional \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . /app/

# Build static assets into the image so each Kubernetes API Pod has them.
# This step does not run database migrations.
RUN python manage.py collectstatic --noinput

RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "medilink.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
