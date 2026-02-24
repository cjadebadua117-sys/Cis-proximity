import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swrs_config.settings')
django.setup()

from presence_app.models import Room

print("Removing duplicate Lab room entries...")
print("="*60)

# We want to keep Lab-1 (Computer Laboratory 1) and remove the others
# Remove duplicates
duplicates_to_remove = [
    "Lab A",
    "Lab B", 
    "Lab 1",  # This is a duplicate
    "Lab 1 (Computer Lab 1)",  # This is also a duplicate
    "Orc (Lab2)",
    "ORC Lab 2"
]

for dup_name in duplicates_to_remove:
    room = Room.objects.filter(name=dup_name).first()
    if room:
        print(f"Deleting: {room.name} (ID: {room.id})")
        room.delete()
        print(f"  ✓ Removed")

print("\n" + "="*60)
print("Remaining Lab rooms:")
for room in Room.objects.filter(name__icontains="lab"):
    print(f"  - {room.name}")
