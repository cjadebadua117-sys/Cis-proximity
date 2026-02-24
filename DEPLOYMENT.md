# CIS-Prox Deployment Guide

Ready to take CIS-Prox from development to production? Follow this guide.

---

## Phase 1: Pre-Deployment Checklist

### Code & Configuration
- [ ] Review all changes in git
- [ ] Update CAMPUS_WIFI_SUBNETS with real campus network ranges
- [ ] Set DEBUG = False
- [ ] Change SECRET_KEY to a new random value
- [ ] Update ALLOWED_HOSTS with actual domain names
- [ ] Enable HTTPS (SECURE_SSL_REDIRECT = True)

### Security
- [ ] Review admin.py customizations (access control)
- [ ] Add rate limiting middleware
- [ ] Configure CORS headers if needed
- [ ] Set up logging and monitoring
- [ ] Plan database backup strategy

### Database
- [ ] Test migrations on staging database
- [ ] Backup current SQLite database
- [ ] Plan migration from SQLite to PostgreSQL (if needed)

### Testing
- [ ] Run full test suite (if exists)
- [ ] Manual sign-in test from campus network
- [ ] Manual sign-in test blocked from off-campus
- [ ] Peer search test
- [ ] Admin interface test
- [ ] Browser compatibility test (Chrome, Firefox, Safari, Edge)

---

## Phase 2: Environment Setup

### Production Server (Ubuntu/Linux Example)

```bash
# 1. Install system dependencies
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv postgresql postgresql-contrib nginx gunicorn

# 2. Create app directory
sudo mkdir -p /opt/cis-prox
cd /opt/cis-prox

# 3. Clone/copy code
cp -r c:\Users\Admin\Desktop\CIS-proximity/* .

# 4. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 5. Install Python dependencies
pip install -r requirements.txt
# If requirements.txt doesn't exist, create it:
pip freeze > requirements.txt
```

### Windows IIS Deployment

```powershell
# 1. Install Python 3.10+ (with pip)
# 2. Create app folder: C:\inetpub\wwwroot\cis-prox
# 3. Copy code to folder
# 4. Create virtual environment
cd C:\inetpub\wwwroot\cis-prox
python -m venv venv
venv\Scripts\activate

# 5. Install dependencies
pip install -r requirements.txt
pip install wfastcgi
```

---

## Phase 3: Database Migration

### From SQLite to PostgreSQL

```bash
# 1. Create PostgreSQL database
sudo -u postgres createdb cis_prox_db
sudo -u postgres createuser cis_prox_user
sudo -u postgres psql << EOF
ALTER USER cis_prox_user WITH PASSWORD 'strong_password';
ALTER ROLE cis_prox_user SET client_encoding TO 'utf8';
GRANT ALL PRIVILEGES ON DATABASE cis_prox_db TO cis_prox_user;
\q
EOF

# 2. Update settings.py
# Change:
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'cis_prox_db',
        'USER': 'cis_prox_user',
        'PASSWORD': 'strong_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# 3. Install PostgreSQL adapter
pip install psycopg2-binary

# 4. Run migrations
python manage.py migrate

# 5. Create superuser
python manage.py createsuperuser

# 6. Collect static files
python manage.py collectstatic --noinput
```

---

## Phase 4: Production Settings

### Update swrs_config/settings.py

```python
# ============== SECURITY ==============
DEBUG = False
SECRET_KEY = 'your-new-random-secret-key-here'  # Generate with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com', '192.168.x.x']

# ============== HTTPS ==============
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# ============== DATABASE ==============
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'cis_prox_db',
        'USER': 'cis_prox_user',
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# ============== LOGGING ==============
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/var/log/cis-prox/django.log',
        },
    },
    'root': {
        'handlers': ['file'],
        'level': 'INFO',
    },
}

# ============== STATIC & MEDIA ==============
STATIC_ROOT = '/var/www/cis-prox/static/'
MEDIA_ROOT = '/var/www/cis-prox/media/'

# ============== CIS-PROX CONFIG ==============
CAMPUS_WIFI_SUBNETS = [
    '192.168.10.0/24',    # Main campus
    '10.20.0.0/16',       # Secondary campus
    '172.16.50.0/24',     # Lab network
]

# ============== EMAIL (for alerts) ==============
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_PASSWORD')
```

---

## Phase 5: Web Server Configuration

### Nginx (Linux/Ubuntu)

Create `/etc/nginx/sites-available/cis-prox`:

```nginx
upstream cis_prox_app {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /etc/ssl/certs/your-cert.crt;
    ssl_certificate_key /etc/ssl/private/your-key.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    client_max_body_size 20M;

    location /static/ {
        alias /var/www/cis-prox/static/;
    }

    location /media/ {
        alias /var/www/cis-prox/media/;
    }

    location / {
        proxy_pass http://cis_prox_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/cis-prox /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## Phase 6: Application Server

### Gunicorn (Linux/Ubuntu)

Create `/etc/systemd/system/cis-prox.service`:

```ini
[Unit]
Description=CIS-Prox Gunicorn Application Server
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/opt/cis-prox
Environment="PATH=/opt/cis-prox/venv/bin"
ExecStart=/opt/cis-prox/venv/bin/gunicorn \
    --workers 4 \
    --worker-class sync \
    --bind 127.0.0.1:8000 \
    --timeout 120 \
    --access-logfile /var/log/cis-prox/access.log \
    --error-logfile /var/log/cis-prox/error.log \
    swrs_config.wsgi:application

[Install]
WantedBy=multi-user.target
```

Start service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable cis-prox
sudo systemctl start cis-prox
sudo systemctl status cis-prox
```

---

## Phase 7: Initial Data Setup

```bash
# 1. Log into admin
http://yourdomain.com/admin/

# 2. Create Rooms
Admin > Room > Add Room
  - Laboratory 1
  - Laboratory 2
  - Room 301
  - Room 302
  - Conference Hall
  - Hallway

# 3. Create Sections (if needed)
Admin > Section > Add Section
  - First Year A
  - First Year B
  - Second Year A
  - etc.

# 4. Test with first user
Register > Sign up as Student
Login
Go to /presence/signin/
Select a room and sign in
Verify PresenceSession created in admin
```

---

## Phase 8: Monitoring & Maintenance

### Logs to Monitor

```bash
# Application logs
tail -f /var/log/cis-prox/django.log

# Web server logs
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log

# System logs
journalctl -u cis-prox -f
```

### Regular Tasks

```bash
# Daily: Check disk space
df -h

# Weekly: Check for expired sessions
python manage.py shell
>>> from presence_app.models import PresenceSession
>>> from django.utils import timezone
>>> from datetime import timedelta
>>> old_sessions = PresenceSession.objects.filter(
...     signed_out_at__lt=timezone.now() - timedelta(days=90)
... )
>>> old_sessions.delete()

# Monthly: Backup database
pg_dump -U cis_prox_user -d cis_prox_db > backup_$(date +%Y%m%d).sql

# Quarterly: Update dependencies
pip list --outdated
pip install --upgrade pip setuptools wheel
```

---

## Phase 9: SSL Certificate (Let's Encrypt)

```bash
# Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# Get certificate
sudo certbot certonly --nginx -d yourdomain.com -d www.yourdomain.com

# Auto-renew
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

---

## Phase 10: Testing & Launch

### Final Checks

- [ ] All endpoints respond (200 OK)
- [ ] HTTPS redirect works
- [ ] Sign-in blocked from off-campus IP
- [ ] Sign-in allowed from campus IP
- [ ] Peer search returns correct results
- [ ] Admin panel fully functional
- [ ] Static files (CSS, JS) load correctly
- [ ] Images/media upload works
- [ ] Email notifications work (if configured)
- [ ] Database backups run automatically
- [ ] Logs are being written

### Launch!

```bash
# Announce to users
# Post on official channels
# Monitor logs during first 24 hours
# Have support team on standby
```

---

## Troubleshooting

### Application won't start
```bash
python manage.py check
python manage.py migrate
systemctl restart cis-prox
```

### Database connection error
```bash
# Test PostgreSQL connection
psql -h localhost -U cis_prox_user -d cis_prox_db
# Should show PostgreSQL prompt
```

### 502 Bad Gateway
```bash
# Check Gunicorn
systemctl status cis-prox
tail -f /var/log/cis-prox/error.log

# Restart if needed
systemctl restart cis-prox
```

### Static files not loading
```bash
python manage.py collectstatic --clear --noinput
```

---

## Security Hardening (Advanced)

### Rate Limiting
Install and configure:
```bash
pip install django-ratelimit
```

### DDoS Protection
- Use Cloudflare or similar CDN
- Configure firewall rules
- Monitor bandwidth usage

### Intrusion Detection
- Install Fail2Ban
- Monitor failed login attempts
- Set up alerts

---

## Rollback Plan

If issues arise after deployment:

```bash
# 1. Check logs
tail -f /var/log/cis-prox/error.log

# 2. Restore previous database backup
psql -U cis_prox_user -d cis_prox_db < backup_20260202.sql

# 3. Revert code to previous commit
git checkout HEAD~1

# 4. Restart application
systemctl restart cis-prox

# 5. Verify
curl https://yourdomain.com/
```

---

## Post-Launch Support

- Monitor error logs daily
- Check admin panel for anomalies
- Respond to user issues
- Schedule monthly security updates
- Document any configuration changes

---

**Version**: 1.0  
**Last Updated**: February 2, 2026  
**Status**: Ready for Production

