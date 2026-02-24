import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swrs_config.settings')
django.setup()

from presence_app.models import Room

# Find Lab-1 and update it
try:
    print("Updating Lab-1...")
    print("="*60)
    
    # Search for Lab-1 room
    lab1 = Room.objects.filter(name__icontains="Lab-1").first() or Room.objects.filter(name__icontains="Laboratory 1").first()
    
    if lab1:
        print(f"Found: {lab1.name}")
        print(f"Updating to: Lab-1 (Computer Laboratory 1)...")
        lab1.name = "Lab-1 (Computer Laboratory 1)"
        lab1.save()
        print("✓ Lab-1 updated successfully!")
    else:
        print("Lab-1 not found. Available rooms:")
        for room in Room.objects.all():
            if 'lab' in room.name.lower():
                print(f"  - {room.name}")
            
except Exception as e:
    print(f"Error: {e}")
