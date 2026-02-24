from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

class Room(models.Model):
    name = models.CharField(max_length=50) # e.g., "Room 1" - "Room 5", "Lab-1", "Orc (Lab2)"
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Section(models.Model):
    """Represents a student section/enrollment (e.g., First Year A-C, Second Year A-B, Third Year SMP/BA, Fourth Year)."""
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


class StudentPresence(models.Model):
    student = models.OneToOneField(User, on_delete=models.CASCADE)
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True)
    current_room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True)
    last_seen = models.DateTimeField(auto_now=True)
    is_online = models.BooleanField(default=False)

    def is_active(self):
        # A student is "Offline" if they haven't been seen in the last 15 minutes
        timeout = timezone.now() - timedelta(minutes=15)
        return self.is_online and self.last_seen > timeout

    def __str__(self):
        return f"{self.student.username} - {self.current_room}"