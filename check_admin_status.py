#!/usr/bin/env python
"""
Verify admin user status
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swrs_config.settings')
django.setup()

from django.contrib.auth.models import User
from presence_app.models import InstructorProfile, UserProfile

try:
    admin = User.objects.get(username='admin')
    print(f"✓ Admin user found")
    print(f"  Username: {admin.username}")
    print(f"  is_staff: {admin.is_staff}")
    print(f"  is_superuser: {admin.is_superuser}")
    print(f"  is_active: {admin.is_active}")
    
    # Check if has InstructorProfile
    try:
        ip = admin.instructor_profile
        print(f"  Has InstructorProfile: YES")
    except InstructorProfile.DoesNotExist:
        print(f"  Has InstructorProfile: NO")
    
    # Check if has UserProfile
    try:
        up = admin.profile
        print(f"  Has UserProfile (student): YES - THIS IS A PROBLEM!")
    except UserProfile.DoesNotExist:
        print(f"  Has UserProfile (student): NO - Good!")
    
except User.DoesNotExist:
    print("✗ Admin user not found in database")
except Exception as e:
    print(f"✗ Error: {e}")
