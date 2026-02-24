import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swrs_config.settings')
django.setup()

from django.contrib.auth.models import User
from presence_app.models import InstructorProfile

# Check christianjade117
user = User.objects.get(username='christianjade117')
print(f"User: {user.username}")
print(f"is_staff: {user.is_staff}")
print(f"is_superuser: {user.is_superuser}")
print(f"Groups: {[g.name for g in user.groups.all()]}")

try:
    prof = user.instructor_profile
    print(f"InstructorProfile: EXISTS")
except:
    print(f"InstructorProfile: DOES NOT EXIST")

print("\n=== All Groups in System ===")
from django.contrib.auth.models import Group
for group in Group.objects.all():
    print(f"Group: {group.name}")
    members = group.user_set.all()
    for member in members:
        print(f"  - {member.username}")
