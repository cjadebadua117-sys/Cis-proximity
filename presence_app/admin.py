"""
CIS-Prox Admin Configuration
=============================

DJANGO GROUPS SETUP (for role-based headers):
============================================

To enable role-based title logic in base.html, you need to create Django Groups.
The template checks: user.is_staff OR user in "Instructors" group.

METHOD 1: Manual Setup via Django Admin
----------------------------------------
1. Go to http://localhost:8000/admin/
2. Under "Authentication and Authorization", click "Groups"
3. Click "Add Group"
4. Name: "Instructors"
5. Leave "Permissions" empty (optional)
6. Click "Save"
7. Then, for each instructor:
   - Go to Users (Authentication and Authorization > Users)
   - Click on the staff user
   - Under "Groups", select "Instructors"
   - Click "Save"

METHOD 2: Programmatic Setup (Python Shell)
--------------------------------------------
Open Django shell: python manage.py shell

from django.contrib.auth.models import Group
instructors_group, created = Group.objects.get_or_create(name="Instructors")
print(f"Instructors group {'created' if created else 'already exists'}")

# Add a user to the group
from django.contrib.auth.models import User
user = User.objects.get(username="your_instructor_username")
user.groups.add(instructors_group)
print(f"Added {user.username} to Instructors group")

METHOD 3: Using Management Command
-----------------------------------
Create a file: presence_app/management/commands/setup_groups.py
Then run: python manage.py setup_groups [add_user_option]

NOTE: The `has_group` template filter in templatetags/utils_tags.py enables
      group membership checks in templates. This is automatically loaded
      with {% load utils_tags %} in base.html.
"""

from django.contrib import admin
from .models import Room, StudentPresence, Section, UserProfile, InstructorProfile, Broadcast, SignInRecord, FlagRaisingCeremony, ActivityHour, PresenceSession, LaboratoryHistory

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')

@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'year', 'section', 'program')
    list_filter = ('year', 'program')
    ordering = ('year', 'section')

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'created_at')
    search_fields = ('user__username', 'user__email')

@admin.register(InstructorProfile)
class InstructorProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'section', 'instructor_room', 'allow_off_network', 'created_at')
    list_filter = ('section', 'instructor_room', 'allow_off_network')
    list_editable = ('section', 'instructor_room', 'allow_off_network')
    search_fields = ('user__username', 'user__email')


@admin.register(Broadcast)
class BroadcastAdmin(admin.ModelAdmin):
    list_display = ('room', 'message', 'created_at')
    readonly_fields = ('created_at',)
    list_filter = ('room',)


@admin.register(StudentPresence)
class StudentPresenceAdmin(admin.ModelAdmin):
    list_display = ('student', 'section', 'current_room', 'is_online')
    list_filter = ('section', 'is_online')

@admin.register(SignInRecord)
class SignInRecordAdmin(admin.ModelAdmin):
    list_display = ('student', 'room', 'sign_in_time', 'sign_out_time')
    list_filter = ('room', 'sign_in_time')
    search_fields = ('student__username',)
    readonly_fields = ('sign_in_time',)

@admin.register(FlagRaisingCeremony)
class FlagRaisingCeremonyAdmin(admin.ModelAdmin):
    list_display = ('student', 'attendance_date', 'present')
    list_filter = ('present', 'attendance_date')
    search_fields = ('student__username',)

@admin.register(ActivityHour)
class ActivityHourAdmin(admin.ModelAdmin):
    list_display = ('student', 'sign_in_time', 'sign_out_time', 'is_active')
    list_filter = ('sign_in_time',)
    search_fields = ('student__username',)
    readonly_fields = ('sign_in_time', 'recorded_at')
    
    def is_active(self, obj):
        return "🟢 Active" if obj.is_active() else "✓ Completed"
    
    is_active.short_description = "Status"  # type: ignore

@admin.register(PresenceSession)
class PresenceSessionAdmin(admin.ModelAdmin):
    """Admin interface for CIS-Prox presence sessions."""
    list_display = ('user', 'room', 'status_indicator', 'signed_in_at', 'duration', 'ip_address')
    list_filter = ('is_active', 'is_verified', 'room', 'signed_in_at')
    search_fields = ('user__username', 'user__email', 'ip_address')
    readonly_fields = ('signed_in_at', 'ip_address', 'duration_display')
    ordering = ['-signed_in_at']
    
    fieldsets = (
        ('User & Location', {
            'fields': ('user', 'room')
        }),
        ('Network Verification', {
            'fields': ('ip_address', 'is_verified'),
            'classes': ('collapse',),
        }),
        ('Session Timing', {
            'fields': ('signed_in_at', 'signed_out_at', 'duration_display')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
    
    def status_indicator(self, obj):
        """Show active/inactive status with emoji."""
        if obj.is_active:
            return "🟢 Active"
        else:
            return "🔴 Signed Out"
    status_indicator.short_description = "Status"
    
    def duration(self, obj):
        """Display duration in human-readable format."""
        minutes = obj.duration_minutes()
        hours = minutes // 60
        mins = minutes % 60
        if hours > 0:
            return f"{hours}h {mins}m"
        return f"{mins}m"
    duration.short_description = "Duration"
    
    def duration_display(self, obj):
        """Full duration display for readonly field."""
        return f"{obj.duration_minutes()} minutes"
    duration_display.short_description = "Total Duration"


@admin.register(LaboratoryHistory)
class LaboratoryHistoryAdmin(admin.ModelAdmin):
    """Admin interface for automatic Laboratory History exit tracking."""
    date_hierarchy = 'exit_time'
    list_display = ('student', 'room_name', 'exit_time', 'duration_display')
    list_filter = ('room', 'exit_time')
    search_fields = ('student__username', 'student__email', 'room__name')
    readonly_fields = ('exit_time', 'student', 'room', 'duration_minutes')
    ordering = ['-exit_time']
    
    fieldsets = (
        ('Student & Location', {
            'fields': ('student', 'room')
        }),
        ('Exit Record', {
            'fields': ('exit_time', 'duration_minutes')
        }),
    )
    
    def room_name(self, obj):
        """Display room name in list view."""
        return obj.room.name if obj.room else "Unknown Lab"
    room_name.short_description = "Lab Room"
    
    def duration_display(self, obj):
        """Display duration in human-readable format."""
        if obj.duration_minutes >= 60:
            hours = obj.duration_minutes // 60
            mins = obj.duration_minutes % 60
            return f"{hours}h {mins}m"
        return f"{obj.duration_minutes}m"
    duration_display.short_description = "Duration"