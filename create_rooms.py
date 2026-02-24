import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swrs_config.settings')
django.setup()

from presence_app.models import Room, Section

# Create rooms
rooms = [
    {'name': 'Room 1 (Classroom 1)', 'description': ''},
    {'name': 'Room 2 (Classroom 2)', 'description': ''},
    {'name': 'Room 3 (Classroom 3)', 'description': ''},
    {'name': 'Room 4 (Classroom 4)', 'description': ''},
    {'name': 'Room 5 (Classroom 5)', 'description': ''},
    {'name': 'Lab 1 (Computer Lab 1)', 'description': ''},
    {'name': 'ORC (Computer Lab 2)', 'description': ''},
    {'name': 'Faculty 1', 'description': 'Faculty Office 1'},
    {'name': 'Faculty 2', 'description': 'Faculty Office 2'},
    {'name': 'Student Lounge', 'description': 'Default location for students when not in a room'},
]

print("Creating rooms...")
for room_data in rooms:
    room, created = Room.objects.get_or_create(
        name=room_data['name'],
        defaults={'description': room_data['description']}
    )
    if created:
        print(f"  Created room: {room.name}")
    else:
        print(f"  Room already exists: {room.name}")

# Create sections
sections = [
    # First Year: A, B, C
    {'year': '1', 'section': 'A', 'program': 'GENERAL'},
    {'year': '1', 'section': 'B', 'program': 'GENERAL'},
    {'year': '1', 'section': 'C', 'program': 'GENERAL'},
    
    # Second Year: A, B
    {'year': '2', 'section': 'A', 'program': 'GENERAL'},
    {'year': '2', 'section': 'B', 'program': 'GENERAL'},
    
    # Third Year: SMP and BA
    {'year': '3', 'section': 'SMP', 'program': 'SMP'},
    {'year': '3', 'section': 'BA', 'program': 'BA'},
    
    # Fourth Year: 1 Section
    {'year': '4', 'section': 'A', 'program': 'GENERAL'},
]

print("\nCreating sections...")
for section_data in sections:
    section, created = Section.objects.get_or_create(
        year=section_data['year'],
        section=section_data['section'],
        program=section_data['program'],
    )
    if created:
        print(f"  Created section: {section}")
    else:
        print(f"  Section already exists: {section}")

print("\nDone!")

