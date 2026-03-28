from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a UserProfile when a new User is created (but not for staff/superuser accounts)."""
    if created:
        # Don't create UserProfile for staff or superuser accounts
        # They should use InstructorProfile instead
        if not instance.is_staff and not instance.is_superuser:
            UserProfile.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save the UserProfile when the User is saved (but not for staff/superuser accounts)."""
    # Skip saving UserProfile for staff/superuser accounts
    if instance.is_staff or instance.is_superuser:
        return
    
    try:
        instance.profile.save()
    except UserProfile.DoesNotExist:
        # Only create if not staff/superuser
        if not instance.is_staff and not instance.is_superuser:
            UserProfile.objects.create(user=instance)
