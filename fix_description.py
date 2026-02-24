import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swrs_config.settings')
django.setup()

from presence_app.models import Room

print("Fixing room descriptions...")
print("="*60)

# Find Lab-1 and clear its description
lab1 = Room.objects.filter(name__icontains="Lab-1").first()
if lab1:
    print(f"Found: {lab1.name}")
    print(f"Old description: '{lab1.description}'")
    lab1.description = ""  # Clear description
    lab1.save()
    print(f"New description: '{lab1.description}'")
    print("✓ Lab-1 description cleared!")
    
print("\nAll rooms with descriptions:")
rooms_with_desc = Room.objects.exclude(description="")
for room in rooms_with_desc:
    print(f"  - {room.name}: '{room.description}'")
