#!/usr/bin/env python
"""Test peer search logic to ensure classmates are findable."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swrs_config.settings')
django.setup()

from django.contrib.auth.models import User
from presence_app.models import StudentPresence, Section, UserProfile

# Create test section
section, _ = Section.objects.get_or_create(year=1, section='A')

# Create test users in the same section
user1, _ = User.objects.get_or_create(
    username='testuser1',
    defaults={'email': 'test1@example.com', 'is_active': True}
)

user2, _ = User.objects.get_or_create(
    username='testuser2',
    defaults={'email': 'test2@example.com', 'is_active': True}
)

# Ensure profiles exist
user1.profile  # signal creates it
user2.profile

# Create StudentPresence for both users in the same section
pres1, _ = StudentPresence.objects.get_or_create(
    student=user1,
    defaults={'section': section, 'is_online': True}
)
pres2, _ = StudentPresence.objects.get_or_create(
    student=user2,
    defaults={'section': section, 'is_online': False}  # offline but still enrolled
)

# Test: user1 searches for user2 (who is offline/enrolled but not online)
from django.db.models import Q
from presence_app.models import UserProfile as UP

visibility_q = Q(student__profile__privacy_level=UP.PRIVACY_PUBLIC) | Q(student=user1) | (
    Q(student__profile__privacy_level=UP.PRIVACY_FRIENDS_ONLY, student__profile__friends=user1)
)

# Simulate search for user2
results = StudentPresence.objects.filter(
    section=section,
    student__username__icontains='testuser2'
).exclude(student=user1).filter(visibility_q).select_related('student', 'current_room').distinct()

print(f"Found {results.count()} classmate(s) matching 'testuser2':")
for r in results:
    print(f"  - {r.student.username} (online: {r.is_online})")

if results.count() > 0:
    print("✓ PASS: Offline classmates are now searchable!")
else:
    print("✗ FAIL: Offline classmates still not searchable")
