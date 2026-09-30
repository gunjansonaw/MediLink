#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Collect static files with Whitenoise
python manage.py collectstatic --no-input

# Run database migrations
python manage.py migrate --no-input
