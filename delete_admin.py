#!/usr/bin/env python
"""Delete admin user account and all related records."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swrs_config.settings')
django.setup()

from django.contrib.auth.models import User
from presence_app.models import FlagRaisingCeremony, StudentPresence, InstructorProfile

# First check if admin exists
admin = User.objects.filter(username='admin').first()
if not admin:
    print('✗ Admin user not found in database')
    exit(0)

print(f'Found admin user (ID: {admin.id})')

# Delete related FlagRaisingCeremony records
frc_count, _ = FlagRaisingCeremony.objects.filter(student=admin).delete()
print(f'  - Deleted {frc_count} FRC records')

# Delete related StudentPresence records  
presence_count, _ = StudentPresence.objects.filter(student=admin).delete()
print(f'  - Deleted {presence_count} StudentPresence records')

# Delete related InstructorProfile records
instructor_count, _ = InstructorProfile.objects.filter(user=admin).delete()
print(f'  - Deleted {instructor_count} InstructorProfile records')

# Finally delete the user account
user_count, _ = User.objects.filter(username='admin').delete()
print(f'  - Deleted {user_count} User accounts')

# Verify
remaining = User.objects.filter(username='admin').exists()
print(f'\n✓ Admin deleted successfully')
print(f'✓ Admin still exists: {remaining}')
