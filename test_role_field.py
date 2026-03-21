#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swrs_config.settings')
django.setup()

from django.contrib.auth.models import User
from presence_app.models import UserProfile, InstructorProfile

try:
    u = User.objects.get(username='leanne')
    p = u.profile
    print('=== UserProfile for leanne ===')
    print('Has role field:', hasattr(p, 'role'))
    print('All fields on UserProfile:')
    for field in p._meta.get_fields():
        print(f'  - {field.name}: {field.get_internal_type()}')
    
    print('\n=== Check InstructorProfile ===')
    try:
        instr = u.instructor_profile
        print('Has InstructorProfile: YES')
        print('InstructorProfile data:', instr.__dict__)
    except InstructorProfile.DoesNotExist:
        print('Has InstructorProfile: NO')
    
    print('\n=== UserProfile instance dict ===')
    print(p.__dict__)
    
except User.DoesNotExist:
    print('User leanne does not exist')
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
