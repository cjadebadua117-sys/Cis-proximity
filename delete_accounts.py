#!/usr/bin/env python
"""Delete all user accounts (students and instructors)."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swrs_config.settings')
django.setup()

from django.contrib.auth.models import User

# Count before deletion
before = User.objects.count()

# Delete all users
User.objects.all().delete()

# Count after deletion
after = User.objects.count()

print(f"✓ Deleted {before} user accounts")
print(f"✓ Remaining users: {after}")
