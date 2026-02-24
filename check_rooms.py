import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swrs_config.settings')
django.setup()

from presence_app.models import Room

print("=== All Rooms in Database ===")
all_rooms = Room.objects.all().order_by('name')
for room in all_rooms:
    print(f"Name: '{room.name}'")

print("\n=== Room Names (quoted) ===")
for room in all_rooms:
    print(f"'{room.name}'")
