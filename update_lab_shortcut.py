import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swrs_config.settings')
django.setup()

from presence_app.models import Room

print("Updating room name...")
print("="*60)

# Find Lab-1 and update it
lab1 = Room.objects.filter(name__icontains="Lab-1").first()
if lab1:
    print(f"Found: {lab1.name}")
    print(f"Updating to: Lab-1 (Computer Lab 1)...")
    lab1.name = "Lab-1 (Computer Lab 1)"
    lab1.save()
    print("✓ Lab-1 updated successfully!")
    print(f"New name: {lab1.name}")
else:
    print("Lab-1 not found.")
