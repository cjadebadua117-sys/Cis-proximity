import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swrs_config.settings')
django.setup()

from presence_app.models import Room

print("Removing Information Systems Lab description...")
print("="*60)

# Find Room 4 and clear its description
room4 = Room.objects.filter(name__icontains="Room 4").first()
if room4:
    print(f"Found: {room4.name}")
    print(f"Old description: '{room4.description}'")
    room4.description = ""  # Clear description
    room4.save()
    print(f"New description: '{room4.description}'")
    print("✓ Room 4 description cleared!")
else:
    print("Room 4 not found.")
