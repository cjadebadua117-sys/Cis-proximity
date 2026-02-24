import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swrs_config.settings')
django.setup()

from presence_app.models import StudentPresence, LaboratoryHistory, Section, SignInRecord, InstructorProfile
from django.contrib.auth.models import User

print("=" * 50)
print("DETAILED ANALYSIS")
print("=" * 50)

# Get all instructors and their sections
print("\nInstructors and their sections:")
instructors = InstructorProfile.objects.select_related('user', 'section')
for instr in instructors:
    print(f"  - {instr.user.username}: Section = {instr.section}")

# Check student sections
print("\nStudent sections:")
students = StudentPresence.objects.select_related('student', 'section')
for student in students:
    print(f"  - {student.student.username}: Section = {student.section}")

# Check all LaboratoryHistory records
print("\nAll Laboratory History records:")
lab_histories = LaboratoryHistory.objects.all()
for lab in lab_histories:
    print(f"  - Student: {lab.student.username if lab.student else 'None'}, Room: {lab.room.name if lab.room else 'None'}, Exit: {lab.exit_time}")

# Check which sign_ins created lab history
print("\nSignInRecords with sign_out_time (completed sessions):")
completed = SignInRecord.objects.filter(sign_out_time__isnull=False)
for rec in completed:
    print(f"  - Student: {rec.student.username}, Room: {rec.room.name}, Duration: {rec.duration_minutes()}")

# Let's see the section filtering
print("\n" + "=" * 50)
print("TESTING THE VIEW QUERY")
print("=" * 50)

# Simulate what the laboratory_history view does
for instr in instructors:
    if instr.section:
        print(f"\nInstructor: {instr.user.username}, Section: {instr.section}")
        
        # This is the query from the view
        qs = LaboratoryHistory.objects.select_related('student', 'room').filter(
            student__studentpresence__section=instr.section
        ).order_by('-exit_time')
        
        print(f"  Query count: {qs.count()}")
        for r in qs:
            print(f"    - {r.student.username}, Room: {r.room.name if r.room else 'None'}, Exit: {r.exit_time}")
