#!/bin/bash

# MediLink Deployment Script for AWS EC2

echo "Starting MediLink deployment..."

# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install required packages
sudo apt-get install -y python3-pip python3-venv nginx postgresql postgresql-contrib redis-server nodejs npm

# Setup PostgreSQL
sudo -u postgres psql << EOF
CREATE DATABASE medilink;
CREATE USER medilink_user WITH PASSWORD 'your_secure_password';
ALTER ROLE medilink_user SET client_encoding TO 'utf8';
ALTER ROLE medilink_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE medilink_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE medilink TO medilink_user;
\q
EOF

# Create project directory
sudo mkdir -p /var/www/medilink
sudo chown -R $USER:$USER /var/www/medilink
cd /var/www/medilink

# Clone or copy your repository
# git clone https://github.com/yourusername/medilink.git .

# Backend setup
cd /var/www/medilink/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env file
cat > .env << EOF
SECRET_KEY=$(python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
DEBUG=False
ALLOWED_HOSTS=your_domain.com,your_ec2_ip
DB_NAME=medilink
DB_USER=medilink_user
DB_PASSWORD=your_secure_password
DB_HOST=localhost
DB_PORT=5432
CORS_ALLOWED_ORIGINS=https://your_domain.com
EOF

# Run migrations
python manage.py makemigrations
python manage.py migrate
python manage.py collectstatic --noinput

# Create superuser (interactive)
echo "Create Django superuser:"
python manage.py createsuperuser

# Frontend setup
cd /var/www/medilink/frontend
npm install
cat > .env << EOF
REACT_APP_API_URL=https://your_domain.com/api
EOF
npm run build

# Setup Gunicorn service
sudo mkdir -p /var/log/medilink
sudo cp /var/www/medilink/deployment/gunicorn.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start gunicorn
sudo systemctl enable gunicorn

# Setup Nginx
sudo cp /var/www/medilink/deployment/nginx.conf /etc/nginx/sites-available/medilink
sudo ln -s /etc/nginx/sites-available/medilink /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Setup firewall
sudo ufw allow 'Nginx Full'
sudo ufw allow OpenSSH
sudo ufw enable

# Start Redis
sudo systemctl start redis-server
sudo systemctl enable redis-server

echo "Deployment completed successfully!"
echo "Access your application at: http://your_domain.com"
echo "Admin panel at: http://your_domain.com/admin"
echo "API documentation at: http://your_domain.com/swagger"
