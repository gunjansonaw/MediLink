# -----------------------------------------------------------
# MediLink Backend - Production Dockerfile
# Python 3.11 Slim with Multi-Stage Optimization
# -----------------------------------------------------------
FROM python:3.11-slim

# Prevent Python from writing .pyc files & buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies (PostgreSQL client libraries, netcat for DB polling)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    netcat-traditional \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY . /app/

# Make entrypoint script executable
RUN chmod +x /app/entrypoint.sh

# Expose Django REST API port
EXPOSE 8000

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command: Run production Gunicorn WSGI server
CMD ["gunicorn", "medilink.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
