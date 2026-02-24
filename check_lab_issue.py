import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swrs_config.settings')
django.setup()

from presence_app.models import StudentPresence, LaboratoryHistory, Section, SignInRecord
from django.contrib.auth.models import User

print("=" * 50)
print("DATABASE ANALYSIS")
print("=" * 50)

# Check students with no section
students_no_section = StudentPresence.objects.filter(section__isnull=True).count()
print(f"Students with no section: {students_no_section}")

# Check total students
total_students = StudentPresence.objects.count()
print(f"Total students: {total_students}")

# Check total lab history records
total_lab_history = LaboratoryHistory.objects.count()
print(f"Total Lab History records: {total_lab_history}")

# Check total sign-in records with sign_out_time (completed sessions)
completed_signins = SignInRecord.objects.filter(sign_out_time__isnull=False).count()
print(f"Completed SignIn Records: {completed_signins}")

# Check total sign-in records (all)
all_signins = SignInRecord.objects.count()
print(f"All SignIn Records: {all_signins}")

# Check if there are any sections
sections = Section.objects.count()
print(f"Total Sections: {sections}")

# Check some sample data
print("\n" + "=" * 50)
print("SAMPLE DATA")
print("=" * 50)

print("\nRecent SignIn Records (last 5):")
for r in SignInRecord.objects.all()[:5]:
    print(f"  - Student: {r.student.username}, Room: {r.room.name if r.room else 'None'}, SignIn: {r.sign_in_time}, SignOut: {r.sign_out_time}")

print("\nRecent Laboratory History Records (last 5):")
for r in LaboratoryHistory.objects.all()[:5]:
    print(f"  - Student: {r.student.username if r.student else 'None'}, Room: {r.room.name if r.room else 'None'}, Exit: {r.exit_time}, Duration: {r.duration_minutes}m")
