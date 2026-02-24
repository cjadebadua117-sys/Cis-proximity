import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swrs_config.settings')
django.setup()

from django.contrib.auth.models import User
from presence_app.models import InstructorProfile

print("=== Instructors in Database ===")
instructors = InstructorProfile.objects.all()
for profile in instructors:
    print(f"User: {profile.user.username} | Email: {profile.user.email}")

if not instructors:
    print("NO INSTRUCTORS FOUND")

print("\n=== Users with is_staff=True ===")
admins = User.objects.filter(is_staff=True)
for user in admins:
    print(f"User: {user.username} | Email: {user.email}")

if not admins:
    print("NO ADMIN USERS FOUND")
