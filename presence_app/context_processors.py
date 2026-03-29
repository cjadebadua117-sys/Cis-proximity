"""
Context processors for presence_app.
These functions add data to the context of every template rendered.
"""
from presence_app.models import InstructorProfile


def is_instructor(request):
    """
    Add is_instructor and is_admin flags to all templates.
    Returns True for is_instructor if the user is an InstructorProfile (excluding admins).
    Returns True for is_admin if the user is staff or superuser.
    """
    if not request.user.is_authenticated:
        return {'is_instructor': False, 'is_admin': False}
    
    # Check if user is admin (staff or superuser)
    if request.user.is_staff or request.user.is_superuser:
        return {'is_instructor': False, 'is_admin': True}
    
    # Check if user has InstructorProfile
    try:
        request.user.instructor_profile
        return {'is_instructor': True, 'is_admin': False}
    except InstructorProfile.DoesNotExist:
        pass
    
    return {'is_instructor': False, 'is_admin': False}
