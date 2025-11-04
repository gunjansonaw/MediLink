# MediLink Deployment Guide

Complete deployment instructions for AWS EC2 with Nginx and PostgreSQL

## Prerequisites

- AWS EC2 instance (Ubuntu 20.04 or later)
- Domain name (optional but recommended)
- SSH access to your server

## Quick Deployment

1. **Connect to your EC2 instance**:
```bash
ssh -i your-key.pem ubuntu@your-ec2-ip
```

2. **Upload deployment files**:
```bash
scp -i your-key.pem -r deployment ubuntu@your-ec2-ip:/home/ubuntu/
```

3. **Run deployment script**:
```bash
chmod +x deployment/deploy.sh
./deployment/deploy.sh
```

## Manual Deployment Steps

### 1. System Setup

```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y python3-pip python3-venv nginx postgresql postgresql-contrib redis-server nodejs npm
```

### 2. PostgreSQL Setup

```bash
sudo -u postgres psql
CREATE DATABASE medilink;
CREATE USER medilink_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE medilink TO medilink_user;
\q
```

### 3. Backend Deployment

```bash
cd /var/www/medilink/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with production values

# Run migrations
python manage.py migrate
python manage.py collectstatic
python manage.py createsuperuser
```

### 4. Frontend Deployment

```bash
cd /var/www/medilink/frontend
npm install
npm run build
```

### 5. Gunicorn Setup

```bash
sudo cp deployment/gunicorn.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start gunicorn
sudo systemctl enable gunicorn
```

### 6. Nginx Configuration

```bash
sudo cp deployment/nginx.conf /etc/nginx/sites-available/medilink
sudo ln -s /etc/nginx/sites-available/medilink /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 7. SSL Certificate (Optional)

```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d your_domain.com
```

## Environment Variables

### Backend (.env)
```
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=your_domain.com,your_ip
DB_NAME=medilink
DB_USER=medilink_user
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
```

### Frontend (.env)
```
REACT_APP_API_URL=https://your_domain.com/api
```

## Security Checklist

- [ ] Change default PostgreSQL password
- [ ] Update SECRET_KEY in Django
- [ ] Set DEBUG=False in production
- [ ] Configure proper ALLOWED_HOSTS
- [ ] Enable firewall (ufw)
- [ ] Setup SSL certificate
- [ ] Configure CORS properly
- [ ] Secure media/static file permissions

## Monitoring & Maintenance

### Check service status
```bash
sudo systemctl status gunicorn
sudo systemctl status nginx
sudo systemctl status postgresql
```

### View logs
```bash
# Application logs
sudo tail -f /var/log/medilink/error.log

# Nginx logs
sudo tail -f /var/nginx/error.log

# Gunicorn logs
sudo journalctl -u gunicorn
```

### Restart services
```bash
sudo systemctl restart gunicorn
sudo systemctl restart nginx
```

## Backup Strategy

### Database Backup
```bash
pg_dump medilink > backup_$(date +%Y%m%d).sql
```

### Media Files Backup
```bash
tar -czf media_backup_$(date +%Y%m%d).tar.gz /var/www/medilink/backend/media/
```

## Troubleshooting

### Application not accessible
- Check Gunicorn status
- Verify Nginx configuration
- Check firewall rules
- Review error logs

### Database connection issues
- Verify PostgreSQL is running
- Check database credentials
- Ensure proper permissions

### Static files not loading
- Run `python manage.py collectstatic`
- Check Nginx static file configuration
- Verify file permissions

## Performance Optimization

1. **Enable Gzip compression** in Nginx
2. **Configure caching** for static assets
3. **Use PostgreSQL connection pooling**
4. **Setup Redis** for session storage
5. **Enable CDN** for static files (optional)

## Support

For issues and questions, refer to the main README or create an issue in the repository.
