#!/usr/bin/env python
"""
Create admin superuser account
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swrs_config.settings')
django.setup()

from django.contrib.auth.models import User

# Delete any existing admin account first
User.objects.filter(username='admin').delete()

# Create new admin superuser
admin = User.objects.create_superuser(
    username='admin',
    email='admin@cisproximity.edu',
    password='AdminPassword123!'
)

print(f"✓ Admin superuser created successfully!")
print(f"  Username: {admin.username}")
print(f"  Email: {admin.email}")
print(f"  is_staff: {admin.is_staff}")
print(f"  is_superuser: {admin.is_superuser}")
print(f"\n  Login credentials:")
print(f"    URL: http://127.0.0.1:8000/login/")
print(f"    Username: admin")
print(f"    Password: AdminPassword123!")
