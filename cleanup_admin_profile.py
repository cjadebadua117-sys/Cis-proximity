#!/usr/bin/env python
"""
Clean up admin user's student profile
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swrs_config.settings')
django.setup()

from django.contrib.auth.models import User
from presence_app.models import UserProfile

# Delete UserProfile for admin user
try:
    admin = User.objects.get(username='admin')
    deleted_count, _ = UserProfile.objects.filter(user=admin).delete()
    print(f"✓ Deleted {deleted_count} UserProfile record(s) for admin user")
    print(f"  Admin account: is_staff={admin.is_staff}, is_superuser={admin.is_superuser}")
except User.DoesNotExist:
    print("✗ Admin user not found")
except Exception as e:
    print(f"✗ Error: {e}")
