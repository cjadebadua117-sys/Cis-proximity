"""Management command to create test lab history records for debugging."""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from presence_app.models import LaboratoryHistory, LegacyLaboratoryHistory, Room
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Create test lab history records for instructor view debugging'

    def handle(self, *args, **options):
        # Get or create a test student
        test_user, created = User.objects.get_or_create(
            username='teststudent',
            defaults={'email': 'test@example.com', 'first_name': 'Test', 'last_name': 'Student'}
        )
        
        # Get or create a lab room
        lab_room, created = Room.objects.get_or_create(
            name='Lab 1',
            defaults={'description': 'Chemistry Lab Room 1'}
        )

        # Try to create a lab history record using the modern model
        try:
            record = LaboratoryHistory.objects.create(
                student=test_user,
                room=lab_room,
                exit_time=timezone.now() - timedelta(hours=2),
                duration_minutes=120
            )
            self.stdout.write(
                self.style.SUCCESS(f'✓ Created modern lab history record: {record}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Failed to create modern record: {e}')
            )
            # Try legacy model
            try:
                legacy_record = LegacyLaboratoryHistory.objects.create(
                    lab_room_number='Lab 1',
                    entry_time=timezone.now() - timedelta(hours=2),
                    purpose_of_visit='exit',
                    student_id=test_user.id
                )
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created legacy lab history record: {legacy_record}')
                )
            except Exception as e2:
                self.stdout.write(
                    self.style.ERROR(f'✗ Failed to create legacy record: {e2}')
                )

        # Create another for ORC Lab
        orc_lab, created = Room.objects.get_or_create(
            name='ORC Lab 2',
            defaults={'description': 'ORC Lab Room 2'}
        )

        try:
            record2 = LaboratoryHistory.objects.create(
                student=test_user,
                room=orc_lab,
                exit_time=timezone.now() - timedelta(hours=1),
                duration_minutes=60
            )
            self.stdout.write(
                self.style.SUCCESS(f'✓ Created modern lab history record: {record2}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Failed to create modern record: {e}')
            )

        self.stdout.write(self.style.SUCCESS('\n✓ Test lab history records created'))
        self.stdout.write('Go to /laboratory/history/ as an instructor to view them')
