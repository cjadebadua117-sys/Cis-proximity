import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swrs_config.settings')
django.setup()

from presence_app.models import LegacyLaboratoryHistory
from django.contrib.auth.models import User

records = LegacyLaboratoryHistory.objects.all().order_by('-entry_time')
print('Legacy Lab History Records:')
for r in records:
    student = User.objects.filter(pk=r.student_id).first()
    print(f"  ID: {r.id} | Room: {r.lab_room_number} | Student: {student.username if student else 'N/A'} | Time: {r.entry_time}")

print(f"\nTotal: {records.count()}")
