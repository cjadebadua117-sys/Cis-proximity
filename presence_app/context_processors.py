"""
Context processors for presence_app.
These functions add data to the context of every template rendered.
"""
from presence_app.models import InstructorProfile


def is_instructor(request):
    """
    Add is_instructor flag to all templates.
    Returns True if the user is an InstructorProfile or is_staff.
    """
    if not request.user.is_authenticated:
        return {'is_instructor': False}
    
    # Check if user has InstructorProfile
    try:
        request.user.instructor_profile
        return {'is_instructor': True}
    except InstructorProfile.DoesNotExist:
        pass
    
    # Check if user is staff
    if request.user.is_staff:
        return {'is_instructor': True}
    
    return {'is_instructor': False}
