#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swrs_config.settings')
django.setup()

from django.contrib.auth.models import User

u = User.objects.get(username='leanne')
print("=== u.__dict__ ===")
print(u.__dict__)
print("\n=== u.profile.__dict__ ===")
print(u.profile.__dict__)
