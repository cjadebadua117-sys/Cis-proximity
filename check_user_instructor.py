import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swrs_config.settings')
django.setup()

from django.contrib.auth.models import User
from presence_app.models import InstructorProfile

user = User.objects.get(username='cthwojade')
print(f"User: {user.username}")
print(f"  is_staff: {user.is_staff}")
print(f"  is_authenticated: {user.is_authenticated}")

try:
    instructor = user.instructor_profile
    print(f"  has InstructorProfile: True")
    print(f"    section: {instructor.section}")
except InstructorProfile.DoesNotExist:
    print(f"  has InstructorProfile: False")

is_instructor = hasattr(user, 'instructor_profile') or user.is_staff
print(f"\n  Would pass instructor check: {is_instructor}")
