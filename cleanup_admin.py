#!/usr/bin/env python
"""Comprehensive cleanup: Delete admin and verify."""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swrs_config.settings')
django.setup()

from django.contrib.auth.models import User
from presence_app.models import FlagRaisingCeremony, StudentPresence, InstructorProfile

print("=== Admin User Cleanup ===\n")

# Check before
print("BEFORE:")
admin_before = User.objects.filter(username='admin').exists()
print(f"  Admin exists: {admin_before}")
if admin_before:
    admin = User.objects.get(username='admin')
    print(f"  Admin ID: {admin.id}")
    print(f"  Admin is_staff: {admin.is_staff}")
    print(f"  Admin is_superuser: {admin.is_superuser}")
    
    # Check related records
    frc_count = FlagRaisingCeremony.objects.filter(student=admin).count()
    presence_count = StudentPresence.objects.filter(student=admin).count()
    instructor_count = InstructorProfile.objects.filter(user=admin).count()
    print(f"  FRC records: {frc_count}")
    print(f"  StudentPresence records: {presence_count}")
    print(f"  InstructorProfile records: {instructor_count}")

print("\n" + "="*40 + "\n")

# Delete
print("DELETING...")
admin = User.objects.filter(username='admin').first()
if admin:
    frc_count, _ = FlagRaisingCeremony.objects.filter(student=admin).delete()
    presence_count, _ = StudentPresence.objects.filter(student=admin).delete()
    instructor_count, _ = InstructorProfile.objects.filter(user=admin).delete()
    user_count, _ = User.objects.filter(username='admin').delete()
    
    print(f"  ✓ Deleted FRC records: {frc_count}")
    print(f"  ✓ Deleted StudentPresence records: {presence_count}")
    print(f"  ✓ Deleted InstructorProfile records: {instructor_count}")
    print(f"  ✓ Deleted User accounts: {user_count}")
else:
    print("  Admin not found")

print("\n" + "="*40 + "\n")

# Verify
print("AFTER:")
admin_after = User.objects.filter(username='admin').exists()
print(f"  Admin exists: {admin_after}")

if not admin_after:
    print("\n✅ SUCCESS: Admin has been completely removed from the system!")
else:
    print("\n❌ FAILED: Admin still exists in database")
    sys.exit(1)
