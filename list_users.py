#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swrs_config.settings')
django.setup()

from django.contrib.auth.models import User

print("All users in database:")
for user in User.objects.all():
    print(f"  - {user.username} (is_staff={user.is_staff}, is_superuser={user.is_superuser})")

if not User.objects.exists():
    print("  (No users found)")
