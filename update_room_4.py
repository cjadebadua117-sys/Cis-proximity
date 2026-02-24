import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swrs_config.settings')
django.setup()

from presence_app.models import Room

# Find Room 4 and update it
try:
    # First, let's see all rooms
    print("Current rooms in database:")
    for room in Room.objects.all():
        print(f"  ID: {room.id}, Name: {room.name}")
    
    print("\n" + "="*60)
    
    # Update Room 4 - search for any room that contains "Room 4"
    room4 = Room.objects.filter(name__contains="Room 4").first()
    
    if room4:
        print(f"Found: {room4.name}")
        print(f"Updating to: Room 4 (Classroom 4)...")
        room4.name = "Room 4 (Classroom 4)"
        room4.save()
        print("✓ Room updated successfully!")
    else:
        print("Room 4 not found. Available rooms:")
        for room in Room.objects.all():
            print(f"  - {room.name}")
            
except Exception as e:
    print(f"Error: {e}")
