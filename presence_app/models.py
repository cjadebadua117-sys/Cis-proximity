from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta


class Room(models.Model):
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Section(models.Model):
    """Represents a student section (e.g., First Year A, Second Year B, SMP)."""
    YEAR_CHOICES = [
        ('1', 'First Year'),
        ('2', 'Second Year'),
        ('3', 'Third Year'),
        ('4', 'Fourth Year'),
    ]
    
    PROGRAM_CHOICES = [
        ('GENERAL', 'General'),
        ('SMP', 'Service Management Program'),
        ('BA', 'Business Administration'),
    ]
    
    year = models.CharField(max_length=1, choices=YEAR_CHOICES)
    section = models.CharField(max_length=10)  # e.g., 'A', 'B', 'C', 'SMP', 'BA'
    program = models.CharField(max_length=20, choices=PROGRAM_CHOICES, default='GENERAL')
    
    class Meta:
        unique_together = ('year', 'section', 'program')
        ordering = ['year', 'section']
    
    def __str__(self):
        year_display = dict(self.YEAR_CHOICES).get(self.year, self.year)
        if self.program != 'GENERAL':
            return f"{year_display} - {self.program}"
        return f"{year_display} {self.section}"


class UserProfile(models.Model):
    """Extended user profile with additional information."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
    bio = models.TextField(blank=True, max_length=500)
    phone_number = models.CharField(max_length=20, blank=True)
    student_id_number = models.CharField(max_length=12, blank=True, help_text="Format: XXX-XXXX-X (8 digits total)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Privacy controls for location sharing
    PRIVACY_PUBLIC = 'PUBLIC'
    PRIVACY_FRIENDS_ONLY = 'FRIENDS_ONLY'
    PRIVACY_ONLY_ME = 'ONLY_ME'

    PRIVACY_CHOICES = [
        (PRIVACY_PUBLIC, 'Everyone'),
        (PRIVACY_FRIENDS_ONLY, 'Connected users'),
        (PRIVACY_ONLY_ME, 'Only me'),
    ]

    privacy_level = models.CharField(max_length=20, choices=PRIVACY_CHOICES, default=PRIVACY_PUBLIC)

    # Basic friendship relation: users may add other users as friends
    friends = models.ManyToManyField('auth.User', blank=True, related_name='friends_with')
    
    def __str__(self):
        return f"{self.user.username}'s Profile"


class InstructorProfile(models.Model):
    """Profile for instructors with their assigned section (advise class)."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='instructor_profile')
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True)
    # allow off-network sign-ins when instructors are running remote lectures
    allow_off_network = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        section_name = str(self.section) if self.section else "No section"
        return f"{self.user.username} - Instructor ({section_name})"



class Broadcast(models.Model):
    """Message broadcast by an instructor to students in a room."""
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Broadcast in {self.room.name} at {self.created_at:%Y-%m-%d %H:%M}"


class StudentPresence(models.Model):
    student = models.OneToOneField(User, on_delete=models.CASCADE)
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True)
    current_room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True)
    last_seen = models.DateTimeField(auto_now=True)
    is_online = models.BooleanField(default=False)

    def is_active(self):
        timeout = timezone.now() - timedelta(minutes=15)
        return self.is_online and self.last_seen > timeout

    def __str__(self):
        return f"{self.student.username} - {self.current_room}"


class SignInRecord(models.Model):
    """Records all sign-in activities for attendance tracking."""
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sign_in_records')
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    sign_in_time = models.DateTimeField(auto_now_add=True)
    sign_out_time = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-sign_in_time']
    
    def duration_minutes(self):
        """Calculate duration in minutes."""
        if self.sign_out_time:
            delta = self.sign_out_time - self.sign_in_time
            return int(delta.total_seconds() / 60)
        return None
    
    def __str__(self):
        return f"{self.student.username} - {self.room.name} ({self.sign_in_time.strftime('%Y-%m-%d %H:%M')})"


class FlagRaisingCeremony(models.Model):
    """Track Flag Raising Ceremony (FRC) attendance."""
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='frc_attendance')
    attendance_date = models.DateField()
    present = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('student', 'attendance_date')
        ordering = ['-attendance_date']
    
    def get_status(self):
        """Return status: 'success' for attended, 'absent' for not attended."""
        return 'success' if self.present else 'absent'
    
    def __str__(self):
        status = "Present" if self.present else "Absent"
        return f"{self.student.username} - {self.attendance_date} ({status})"


class ActivityHour(models.Model):
    """Track student cleaning activity hours - Wednesday only, sign-in at 1pm."""
    
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_hours')
    
    # Fixed activity: Cleaning
    activity_name = 'Cleaning'
    
    # Sign-in and sign-out tracking (Wednesday only, 1pm start)
    sign_in_time = models.DateTimeField(default=timezone.now)
    sign_out_time = models.DateTimeField(null=True, blank=True)
    
    recorded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-sign_in_time']
    
    def clean(self):
        """Validate that sign-in is only on Wednesday and starts at 1pm or later."""
        from django.core.exceptions import ValidationError
        
        # Check if it's Wednesday (weekday() returns 2 for Wednesday)
        if self.sign_in_time.weekday() != 2:
            raise ValidationError('Activity Hours are only available on Wednesdays.')
        
        # Check if sign-in time is 1pm (13:00) or later
        if self.sign_in_time.hour < 13:
            raise ValidationError('Activity Hours sign-in starts at 1:00 PM. Cannot sign in before 1:00 PM on Wednesday.')
    
    def save(self, *args, **kwargs):
        """Validate before saving."""
        self.clean()
        super().save(*args, **kwargs)
    
    def duration_hours(self):
        """Calculate duration in hours."""
        if self.sign_out_time:
            delta = self.sign_out_time - self.sign_in_time
            return round(delta.total_seconds() / 3600, 1)  # Convert to hours
        return None
    
    def is_active(self):
        """Check if currently signed in."""
        return self.sign_out_time is None
    
    def get_status(self):
        """
        Return status for calendar:
        - 'success': Signed in AND signed out
        - 'partial': Signed in but no sign-out
        - 'absent': No sign-in
        """
        if self.sign_in_time and self.sign_out_time:
            return 'success'  # Green check
        elif self.sign_in_time and not self.sign_out_time:
            return 'partial'  # Red X
        else:
            return 'absent'   # Gray X
    
    def __str__(self):
        status = "Active" if self.is_active() else f"{self.duration_hours()}h"
        return f"{self.student.username} - Cleaning ({status})"


class PresenceSession(models.Model):
    """
    CIS-Prox Core: Real-time presence tracking with network-verified sign-in/sign-out.
    Stores user sessions with room location, IP address, and verification timestamp.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='presence_sessions')
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Network verification
    ip_address = models.GenericIPAddressField()
    is_verified = models.BooleanField(default=True, help_text="IP is on authorized campus subnet")
    
    # Session tracking
    signed_in_at = models.DateTimeField(auto_now_add=True)
    signed_out_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-signed_in_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['is_active', '-signed_in_at']),
        ]
    
    def duration_minutes(self):
        """Calculate session duration in minutes."""
        end_time = self.signed_out_at or timezone.now()
        delta = end_time - self.signed_in_at
        return int(delta.total_seconds() / 60)
    
    def mark_signed_out(self):
        """
        Mark session as signed out.
        Automatically creates a LaboratoryHistory record for exit tracking.
        """
        self.signed_out_at = timezone.now()
        self.is_active = False
        self.save()
        
        # Automatically create Lab History record on exit
        if self.room:  # Only if a room is associated
            LaboratoryHistory.objects.create(
                student=self.user,
                room=self.room,
                duration_minutes=self.duration_minutes()
            )
    
    def __str__(self):
        duration = f"{self.duration_minutes()}m" if not self.is_active else "Active"
        room_name = self.room.name if self.room else "Unknown"
        return f"{self.user.username} - {room_name} ({duration})"


class LaboratoryHistory(models.Model):
    """
    Automatic laboratory exit logbook.
    Records when users exit labs (exit only, entry is not tracked).
    Replaces physical attendance logbooks with digital records.
    """
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lab_visits')
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True, help_text="Lab room")
    exit_time = models.DateTimeField(auto_now_add=True)
    duration_minutes = models.IntegerField(default=0, help_text="How long student was in lab")
    
    class Meta:
        ordering = ['-exit_time']
        verbose_name_plural = "Laboratory History"
        verbose_name = "Lab Exit Record"
    
    def __str__(self):
        room_name = self.room.name if self.room else "Unknown Lab"
        return f"{self.student.username} - exited {room_name} ({self.exit_time.strftime('%Y-%m-%d %H:%M')})"

    @property
    def duration_hours(self):
        """Return whole hours part of duration_minutes."""
        try:
            return int(self.duration_minutes) // 60
        except Exception:
            return 0

    @property
    def duration_minutes_remainder(self):
        """Return remaining minutes after hours have been taken out."""
        try:
            return int(self.duration_minutes) % 60
        except Exception:
            return int(self.duration_minutes or 0)


class LegacyLaboratoryHistory(models.Model):
    """Model mapping for older/legacy lab history table schema.

    This model is non-managed and maps to the existing SQLite table
    `presence_app_laboratoryhistory` when it contains different columns
    (for example `lab_room_number`, `entry_time`, `purpose_of_visit`,
    `student_id`). We keep it non-managed so migrations are not applied
    against it.
    """
    id = models.BigAutoField(primary_key=True)
    lab_room_number = models.CharField(max_length=20, null=True, blank=True)
    entry_time = models.DateTimeField(null=True, blank=True)
    purpose_of_visit = models.TextField(null=True, blank=True)
    student_id = models.IntegerField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'presence_app_laboratoryhistory'

    def __str__(self):
        return f"LegacyLabHistory {self.id} - {self.lab_room_number}"
