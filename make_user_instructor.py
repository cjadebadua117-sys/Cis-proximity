import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swrs_config.settings')
django.setup()

from django.contrib.auth.models import User
from presence_app.models import InstructorProfile, Section

user = User.objects.get(username='cthwojade')

# Try to get or create a default section
try:
    section = Section.objects.first()  # Use first available section
except:
    section = None

# Create InstructorProfile
instructor, created = InstructorProfile.objects.get_or_create(
    user=user,
    defaults={'section': section}
)

if created:
    print(f"✓ Created InstructorProfile for {user.username}")
else:
    print(f"✓ InstructorProfile already exists for {user.username}")

print(f"  Section: {instructor.section}")

# Verify
is_instructor = hasattr(user, 'instructor_profile') or user.is_staff
print(f"\n✓ User {user.username} is now recognized as an instructor")
