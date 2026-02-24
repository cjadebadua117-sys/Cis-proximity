import os
import sys
from datetime import datetime
import pytz

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swrs_config.settings')
import django
django.setup()

from presence_app.models import LegacyLaboratoryHistory
from django.contrib.auth.models import User

UTC = pytz.UTC

# Pick an existing non-superuser user or create one
user = User.objects.filter(is_superuser=False).first()
if not user:
    user = User.objects.create_user('fake_student', 'fake_student@example.com', 'pass')
    user.save()

# Create two legacy entries: Feb 7 and Feb 6, 2026
entries = [
    {'lab_room_number': 'Lab-1', 'entry_time': datetime(2026, 2, 7, 15, 30, tzinfo=UTC), 'purpose_of_visit': 'exit', 'student_id': user.id},
    {'lab_room_number': 'Lab-1', 'entry_time': datetime(2026, 2, 6, 10, 15, tzinfo=UTC), 'purpose_of_visit': 'exit', 'student_id': user.id},
]

for e in entries:
    obj = LegacyLaboratoryHistory.objects.create(
        lab_room_number=e['lab_room_number'],
        entry_time=e['entry_time'],
        purpose_of_visit=e['purpose_of_visit'],
        student_id=e['student_id']
    )
    print('Created legacy record id', obj.id, 'time', obj.entry_time)

print('Done')
