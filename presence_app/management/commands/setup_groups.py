from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, User


class Command(BaseCommand):
    help = 'Set up Django Groups for CIS-Prox role-based access control'

    def add_arguments(self, parser):
        parser.add_argument(
            '--add-instructor',
            type=str,
            help='Username of instructor to add to the Instructors group',
        )
        parser.add_argument(
            '--add-student',
            type=str,
            help='Username of student to add to the Students group',
        )
        parser.add_argument(
            '--list-instructors',
            action='store_true',
            help='List all users in the Instructors group',
        )
        parser.add_argument(
            '--list-students',
            action='store_true',
            help='List all users in the Students group',
        )

    def handle(self, *args, **options):
        # Create required groups
        instructors_group, created = Group.objects.get_or_create(name="Instructors")
        students_group, created = Group.objects.get_or_create(name="Students")
        
        if created:
            self.stdout.write(self.style.SUCCESS("✓ 'Instructors' group created"))
        else:
            self.stdout.write(self.style.WARNING("• 'Instructors' group already exists"))
        
        if created:
            self.stdout.write(self.style.SUCCESS("✓ 'Students' group created"))
        else:
            self.stdout.write(self.style.WARNING("• 'Students' group already exists"))

        # Add instructor to group
        if options['add_instructor']:
            try:
                user = User.objects.get(username=options['add_instructor'])
                user.groups.add(instructors_group)
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Added '{user.username}' to Instructors group")
                )
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"✗ User '{options['add_instructor']}' not found")
                )

        # Add student to group
        if options['add_student']:
            try:
                user = User.objects.get(username=options['add_student'])
                user.groups.add(students_group)
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Added '{user.username}' to Students group")
                )
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"✗ User '{options['add_student']}' not found")
                )

        # List instructors
        if options['list_instructors']:
            instructors = instructors_group.user_set.all()
            if instructors.exists():
                self.stdout.write(self.style.SUCCESS("\nInstructors:"))
                for instructor in instructors:
                    self.stdout.write(f"  • {instructor.username} ({instructor.get_full_name or 'N/A'})")
            else:
                self.stdout.write(self.style.WARNING("\nNo instructors assigned yet"))

        # List students
        if options['list_students']:
            students = students_group.user_set.all()
            if students.exists():
                self.stdout.write(self.style.SUCCESS("\nStudents:"))
                for student in students:
                    self.stdout.write(f"  • {student.username} ({student.get_full_name or 'N/A'})")
            else:
                self.stdout.write(self.style.WARNING("\nNo students assigned yet"))

        if not any([options['add_instructor'], options['add_student'], 
                   options['list_instructors'], options['list_students']]):
            self.stdout.write(self.style.SUCCESS("\n✓ Groups are ready!"))
            self.stdout.write("\nUsage:")
            self.stdout.write("  python manage.py setup_groups --add-instructor <username>")
            self.stdout.write("  python manage.py setup_groups --add-student <username>")
            self.stdout.write("  python manage.py setup_groups --list-instructors")
            self.stdout.write("  python manage.py setup_groups --list-students")
