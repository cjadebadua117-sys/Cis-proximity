# pyright: reportAttributeAccessIssue=false, reportOptionalMemberAccess=false, reportGeneralTypeIssues=false, reportMissingModuleSource=false
import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.views.decorators.http import require_http_methods
from .models import Room, StudentPresence, Section, UserProfile, InstructorProfile, SignInRecord, FlagRaisingCeremony, ActivityHour, PresenceSession, LaboratoryHistory, LegacyLaboratoryHistory, Broadcast
from .utils import is_on_university_wifi, get_client_ip
from django import forms
from django.db.models import Q, Sum, Exists, OuterRef
from django.utils import timezone
from datetime import datetime, timedelta, date
from pytz import timezone as tz
import calendar
import json

logger = logging.getLogger(__name__)
from django.db.utils import OperationalError
from django.http import JsonResponse


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')


class StudentRegistrationForm(UserCreationForm):
    """Registration form for student users."""
    email = forms.EmailField(required=True)
    student_id_number = forms.CharField(
        max_length=12,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'e.g., 241-0273-1'}),
        help_text='Format: XXX-XXXX-X (8 digits total)'
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')


class InstructorRegistrationForm(UserCreationForm):
    """Registration form for instructor users."""
    email = forms.EmailField(required=True)
    section = forms.ModelChoiceField(
        queryset=Section.objects.all(),  # All year levels
        empty_label="-- Select your advise class --",
        label="Advise Class (Section)",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['section'].queryset = Section.objects.all().order_by('year', 'section')  # type: ignore


class StudentRegistrationOnlyForm(UserCreationForm):
    """Registration form for STUDENTS ONLY. Instructors must be created by admins."""
    email = forms.EmailField(required=True)
    student_id_number = forms.CharField(
        max_length=12,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'e.g., 241-0273-1'}),
        help_text='Format: XXX-XXXX-X (8 digits total)'
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def clean_username(self):
        # normalize username to lowercase and strip whitespace; avoid
        # duplicates regardless of case.  returning lowercase ensures we
        # authenticate using the same form during login.
        username = self.cleaned_data.get('username', '').strip().lower()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('A user with that username already exists.')
        return username


class UnifiedRegistrationForm(StudentRegistrationOnlyForm):
    """Legacy compatibility: now same as StudentRegistrationOnlyForm"""
    pass


class EnrollmentForm(forms.Form):
    """Form for students to select their section."""
    section = forms.ModelChoiceField(
        queryset=Section.objects.all(),
        empty_label="-- Select your section --",
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Your Section"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Group sections by year for better UX
        self.fields['section'].queryset = Section.objects.all().order_by('year', 'section')  # type: ignore


class ProfileForm(forms.ModelForm):
    """Form for updating user profile."""
    first_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    
    class Meta:
        model = UserProfile
        fields = ('student_id_number', 'phone_number', 'bio')
        widgets = {
            'student_id_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 241-0273-1'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
        }


class PrivacyForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ('privacy_level',)
        widgets = {
            'privacy_level': forms.Select(attrs={'class': 'privacy-select'})
        }


def home(request):
    """Render the home/landing page with role-based content."""
    context: dict = {
        'is_instructor': False,
        'is_student': False,
    }
    
    if request.user.is_authenticated:
        # Check if user is staff/superuser first
        if request.user.is_staff or request.user.is_superuser:
            context['is_instructor'] = True
            context['instructor_profile'] = None
            context['section'] = None
            context['student_count'] = 0
            context['live_count'] = 0
        else:
            # Check if user is an instructor
            try:
                instructor_profile = request.user.instructor_profile
                context['is_instructor'] = True
                context['instructor_profile'] = instructor_profile
                
                # Get instructor's section and student count
                section = instructor_profile.section
                student_count = StudentPresence.objects.filter(section=section).count()
                # compute how many of those students are currently signed into some room
                live_count = StudentPresence.objects.filter(section=section, current_room__isnull=False, is_online=True).count()
                context['section'] = section
                context['student_count'] = student_count
                context['live_count'] = live_count
            except InstructorProfile.DoesNotExist:
                # User is a student
                context['is_student'] = True
                try:
                    student_presence = request.user.studentpresence
                    context['student_presence'] = student_presence
                    context['section'] = student_presence.section
                except StudentPresence.DoesNotExist:
                    context['needs_enrollment'] = True
    
    return render(request, 'home.html', context)


def register(request):
    """
    Handle user registration for STUDENTS ONLY.
    
    SECURITY NOTE: Instructor accounts can ONLY be created by Django administrators.
    This prevents unauthorized users from gaining instructor privileges.
    """
    # Clear any flash messages that may have been set by other views (e.g. the
    # logout view).  Without this, the "logged out successfully" message would
    # still show up on the registration page after clicking the "Register" link
    # on the login screen.
    for _ in messages.get_messages(request):
        pass

    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        post_data = request.POST.copy()
        form = StudentRegistrationOnlyForm(post_data)
        
        if form.is_valid():
            user = form.save()
            student_id_number = form.cleaned_data.get('student_id_number', '').strip()
            
            # Create student profile with student ID if provided
            if student_id_number:
                user.profile.student_id_number = student_id_number
                user.profile.save()
            
            messages.success(request, '✓ Student account created successfully! You can now log in.')
            login(request, user)
            return redirect('home')

        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f'{field}: {error}')
    else:
        form = StudentRegistrationOnlyForm()

    return render(request, 'register.html', {
        'form': form,
        'is_student_only': True,  # Flag to show student-only message in template
    })

def login_view(request):
    """Handle user login."""
    # clear any leftover flash messages so the login page is always clean
    for _ in messages.get_messages(request):
        pass

    if request.user.is_authenticated:
        return redirect('home')

    # Use Django's built-in authentication form to render errors and keep entered fields.
    form = AuthenticationForm(request=request, data=request.POST or None)

    if request.method == 'POST':
        # Normalize username to lowercase to match registration behavior
        post_data = request.POST.copy()
        post_data['username'] = post_data.get('username', '').lower()
        form = AuthenticationForm(request=request, data=post_data)

        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('dashboard')
        else:
            # authentication failed, show a user-friendly error
            messages.error(request, 'Invalid username or password.')

    return render(request, 'login.html', {'form': form})


@login_required(login_url='login')
def logout_view(request):
    """Handle user logout."""
    logout(request)
    return redirect('login')


@login_required(login_url='login')
def enroll(request):
    """Handle student section enrollment."""
    try:
        current_presence = StudentPresence.objects.get(student=request.user)
    except StudentPresence.DoesNotExist:
        current_presence = None
    
    # If already enrolled, redirect to dashboard
    if current_presence and current_presence.section:
        messages.info(request, f'You are already enrolled in {current_presence.section}.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = EnrollmentForm(request.POST)
        if form.is_valid():
            selected_section = form.cleaned_data['section']

            # if the user is an instructor, update their profile instead
            try:
                instr = request.user.instructor_profile
            except InstructorProfile.DoesNotExist:
                instr = None

            if instr:
                instr.section = selected_section if selected_section else None
                instr.save()
                msg = 'Assignment saved.'
                if selected_section:
                    msg = f'✓ You are now instructor for {selected_section}!'
                else:
                    msg = '✓ You are now a subject instructor (no section assigned).'
                messages.success(request, msg)
                return redirect('dashboard')
            else:
                # student flow
                presence, created = StudentPresence.objects.get_or_create(student=request.user)
                presence.section = selected_section
                presence.save()
                messages.success(request, f'✓ Successfully enrolled in {selected_section}!')
                return redirect('dashboard')
    else:
        form = EnrollmentForm()
    
    # determine whether request.user is an instructor
    is_instr = False
    try:
        if request.user.instructor_profile:
            is_instr = True
    except Exception:
        pass
    
    # Also check if user is staff/superuser
    if request.user.is_staff or request.user.is_superuser:
        is_instr = True

    context = {
        'form': form,
        'is_enrolled': current_presence and current_presence.section,
        'is_instructor': is_instr,
    }
    
    return render(request, 'enroll.html', context)


@login_required(login_url='login')
def dashboard(request):
    """Render the sign-in dashboard."""
    # Restrict admin users from accessing the regular dashboard
    if request.user.is_staff or request.user.is_superuser:
        return redirect('admin:index')
    
    # Check if user is enrolled (students) or is an instructor with a section
    try:
        current_presence = StudentPresence.objects.get(student=request.user)
    except StudentPresence.DoesNotExist:
        current_presence = None

    # Allow instructors (class advisors) who have an assigned section to access without enrolling
    is_instructor_with_section = False
    
    # Check if user is staff/superuser
    if request.user.is_staff or request.user.is_superuser:
        is_instructor_with_section = True
    else:
        try:
            instr = request.user.instructor_profile
            if instr and instr.section:
                is_instructor_with_section = True
        except InstructorProfile.DoesNotExist:
            is_instructor_with_section = False

    # Redirect students without enrollment; instructors with a section are allowed
    if not (is_instructor_with_section or (current_presence and current_presence.section)):
        # previously warned users here, but we no longer show a message
        return redirect('enroll')
    
    # Check if user is on university network
    network_status = 'online' if is_on_university_wifi(request) else 'offline'
    
    # Determine if user is instructor
    is_instructor = False
    if request.user.is_staff or request.user.is_superuser:
        is_instructor = True
        instructor_profile = None
    else:
        try:
            instructor_profile = request.user.instructor_profile
            is_instructor = True
        except InstructorProfile.DoesNotExist:
            instructor_profile = None
            is_instructor = False

    # Filter rooms based on user type
    if is_instructor:
        # INSTRUCTORS: All rooms except Student Lounge
        rooms = Room.objects.exclude(name__icontains='Student Lounge').order_by('name')
    else:
        # STUDENTS: Classrooms + Labs (exclude Faculty and Student Lounge)
        rooms = Room.objects.exclude(name__icontains='Student Lounge').exclude(name__icontains='Faculty').order_by('name')

    # Get current time in Philippines timezone
    philippines_tz = tz('Asia/Manila')
    current_time_ph = timezone.now().astimezone(philippines_tz)
    
    # Resolve active state from both systems (legacy SignInRecord + PresenceSession).
    active_signin_record = _effective_active_signins_qs().filter(
        student=request.user
    ).order_by('-sign_in_time').first()
    active_presence_session = PresenceSession.objects.filter(
        user=request.user,
        is_active=True
    ).order_by('-signed_in_at').first()

    # Check if user has an active sign-in (not signed out yet)
    has_active_signin = bool(active_signin_record or active_presence_session)
    if current_presence:
        active_room = None
        if active_signin_record and active_signin_record.room:
            active_room = active_signin_record.room
        elif active_presence_session and active_presence_session.room:
            active_room = active_presence_session.room

        # Keep current presence in sync for accurate location display.
        if has_active_signin:
            current_presence.is_online = True
            if active_room:
                current_presence.current_room = active_room
        else:
            current_presence.is_online = False

        # Treat signed-out state and legacy "Student Lounge" as outside department.
        if (not has_active_signin) or (
            current_presence.current_room and current_presence.current_room.name == 'Student Lounge'
        ):
            current_presence.current_room = None
    
    # retrieve any active broadcasts for the student's current room
    current_broadcasts = []
    if current_presence and current_presence.current_room:
        current_broadcasts = Broadcast.objects.filter(
            room=current_presence.current_room
        ).order_by('-created_at')[:5]

    context = {
        'network_status': network_status,
        'current_presence': current_presence,
        'rooms': rooms,
        'current_time_ph': current_time_ph,
        'signed_in_at': (
            active_signin_record.sign_in_time
            if active_signin_record else
            (active_presence_session.signed_in_at if active_presence_session else None)
        ),
        'has_active_signin': has_active_signin,
        'is_instructor': is_instructor,
        'instructor_room': instructor_profile.instructor_room if instructor_profile else None,
        'current_broadcasts': current_broadcasts,
    }
    # instanced above
    return render(request, 'dashboard.html', context)


def _is_laboratory_room(room):
    """Best-effort laboratory detector based on room naming conventions."""
    if not room or not getattr(room, 'name', None):
        return False
    room_name = room.name.lower()
    return ('lab' in room_name) or ('orc' in room_name)


def _effective_active_signins_qs():
    """Return active sign-ins excluding stale records superseded by newer rows."""
    newer_rows = SignInRecord.objects.filter(
        student_id=OuterRef('student_id'),
        sign_in_time__gt=OuterRef('sign_in_time')
    )
    return SignInRecord.objects.filter(
        sign_out_time__isnull=True
    ).annotate(
        has_newer_record=Exists(newer_rows)
    ).filter(
        has_newer_record=False
    )


@login_required(login_url='login')
@require_http_methods(["POST"])
def sign_in(request, room_id=None):
    """Handle sign-in to a room."""
    wants_json = (request.headers.get('Content-Type', '') or '').startswith('application/json') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if not is_on_university_wifi(request):
        # allow override if any instructor for this student's section permits off-network
        allow = False
        try:
            student_section = request.user.studentpresence.section
            if student_section:
                # find instructor(s) of that section with override on
                allow = InstructorProfile.objects.filter(section=student_section, allow_off_network=True).exists()
        except Exception:
            allow = False
        if not allow:
            if not wants_json:
                messages.error(request, '❌ You must be connected to University Wi-Fi to enter a room.')
            if wants_json:
                return JsonResponse({'success': False, 'message': 'You must be connected to University Wi-Fi to enter a room.'}, status=403)
            return redirect('dashboard')
    
    # Get room_id from POST data if not in URL
    if room_id is None:
        if wants_json:
            try:
                payload = json.loads(request.body or b'{}')
            except json.JSONDecodeError:
                payload = {}
            room_id = payload.get('room_id') or payload.get('room')
        else:
            room_id = request.POST.get('room_id')
    
    if not room_id:
        if not wants_json:
            messages.error(request, 'Please select a room.')
        if wants_json:
            return JsonResponse({'success': False, 'message': 'Please select a room.'}, status=400)
        return redirect('dashboard')
    
    try:
        room = get_object_or_404(Room, id=room_id)
    except:
        if not wants_json:
            messages.error(request, 'Room not found.')
        if wants_json:
            return JsonResponse({'success': False, 'message': 'Room not found.'}, status=404)
        return redirect('dashboard')
    
    # Get or create student presence record
    presence, created = StudentPresence.objects.get_or_create(student=request.user)

    # Close ALL existing active sign-ins when switching rooms to keep times accurate.
    active_signins = list(
        SignInRecord.objects.filter(
            student=request.user,
            sign_out_time__isnull=True
        ).order_by('-sign_in_time')
    )
    if active_signins:
        if len(active_signins) == 1 and active_signins[0].room_id == room.id:
            if not wants_json:
                messages.info(request, f'You are already signed in to {room.name}.')
            if wants_json:
                return JsonResponse({
                    'success': True,
                    'message': f'You are already signed in to {room.name}.',
                    'room': {'id': room.id, 'name': room.name},
                })
            return redirect('dashboard')

        close_time = timezone.now()
        for active_signin in active_signins:
            active_signin.sign_out_time = close_time
            active_signin.save()
            # If the previous room was a lab, record a corresponding exit row.
            try:
                if _is_laboratory_room(active_signin.room):
                    LaboratoryHistory.objects.create(
                        student=request.user,
                        room=active_signin.room,
                        duration_minutes=active_signin.duration_minutes()
                    )
            except Exception:
                pass
    presence.current_room = room
    presence.is_online = True
    presence.save()
    
    # Record sign-in
    SignInRecord.objects.create(student=request.user, room=room)

    # Log laboratory ENTRY immediately so instructors can see real-time lab history.
    try:
        is_instructor_user = hasattr(request.user, 'instructor_profile')
    except Exception:
        is_instructor_user = False

    if (not is_instructor_user) and _is_laboratory_room(room):
        try:
            LaboratoryHistory.objects.create(
                student=request.user,
                room=room,
                duration_minutes=0
            )
        except Exception:
            # Never block sign-in if history logging fails.
            pass
    
    if created:
        message = f'✓ Signed in to {room.name}'
        if not wants_json:
            messages.success(request, message)
    else:
        message = f'✓ Updated location to {room.name}'
        if not wants_json:
            messages.success(request, message)

    if wants_json:
        return JsonResponse({
            'success': True,
            'message': message,
            'room': {'id': room.id, 'name': room.name},
        })

    return redirect('dashboard')


@login_required(login_url='login')
@require_http_methods(["POST"])
def sign_out(request):
    """Handle sign-out (mark as offline)."""
    wants_json = (request.headers.get('Content-Type', '') or '').startswith('application/json') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    try:
        presence = StudentPresence.objects.get(student=request.user)
        presence.is_online = False
        # Signed-out users should not remain in any room.
        presence.current_room = None
        
        presence.save()

        # Record sign-out time for ALL active sign-ins (defensive cleanup for stale duplicates).
        active_rows = list(SignInRecord.objects.filter(
            student=request.user,
            sign_out_time__isnull=True
        ).order_by('-sign_in_time'))
        close_time = timezone.now()
        for active_row in active_rows:
            active_row.sign_out_time = close_time
            active_row.save()
            # Also create a laboratory exit record so history shows student exits.
            try:
                # Try modern model first (labs only)
                if _is_laboratory_room(active_row.room):
                    LaboratoryHistory.objects.create(
                        student=request.user,
                        room=active_row.room,
                        duration_minutes=active_row.duration_minutes()
                    )
            except Exception:
                # Fallback for legacy DB schema: insert into legacy table if available
                try:
                    if _is_laboratory_room(active_row.room):
                        LegacyLaboratoryHistory.objects.create(
                            lab_room_number=(active_row.room.name if active_row.room else None),
                            entry_time=timezone.now(),
                            purpose_of_visit='exit',
                            student_id=request.user.id
                        )
                except Exception:
                    # If that also fails, ignore to avoid breaking sign-out flow
                    pass

        message = '✓ You have been signed out.'
        if not wants_json:
            messages.success(request, message)
    except StudentPresence.DoesNotExist:
        message = 'No active sign-in found.'
        if not wants_json:
            messages.error(request, message)
        if wants_json:
            return JsonResponse({'success': False, 'message': message}, status=404)

    if wants_json:
        return JsonResponse({'success': True, 'message': message})

    return redirect('dashboard')


@login_required(login_url='login')
def peer_search(request):
    """Search for peers and display their locations.
    
    When a search query is provided, show all classmates (enrolled students in the
    same section) who match the query, whether online or offline. Otherwise, show
    only classmates who are currently online.  Privacy settings are always respected.
    """
    query = request.GET.get('q', '').strip()
    selected_role = request.GET.get('role', 'student').lower().strip()
    if selected_role not in ['student', 'instructor']:
        selected_role = 'student'

    online_title = 'Students Currently Online' if selected_role == 'student' else 'Instructors Currently Online'

    results = None
    online_students = None
    
    # Get current user's section (if enrolled)
    try:
        current_section = request.user.studentpresence.section
    except (StudentPresence.DoesNotExist, AttributeError):
        current_section = None

    # Base queryset with profile preloaded for layout data (photo, student id, phone).
    base_qs = StudentPresence.objects.select_related('student', 'current_room', 'student__profile')

    # Role filtering: students vs instructors.
    if selected_role == 'student':
        # pick only student accounts (exclude instructor profile link)
        base_qs = base_qs.filter(student__instructor_profile__isnull=True)
    else:
        # instructor role; use presence sessions to build the instructor online section list instead.
        # Only show instructors who have instructor_visibility = 'everyone'
        base_qs = base_qs.filter(
            student__instructor_profile__isnull=False,
            student__profile__instructor_visibility=UserProfile.INSTRUCTOR_VISIBILITY_EVERYONE
        )
    
    # Initialize visibility query to avoid UnboundLocalError.
    visibility_q = Q()

    # Privacy filters only apply to students, not instructors
    if selected_role == 'student':
        # For FRIENDS_ONLY, only show if the current user is in the target user's friends list
        if current_section:
            visibility_q |= Q(
                student__profile__privacy_level=UserProfile.PRIVACY_FRIENDS_ONLY,
                student__profile__friends=request.user
            )
        
        # Alternative: check FRIENDS_ONLY without section requirement
        visibility_q |= Q(
            student__profile__privacy_level=UserProfile.PRIVACY_FRIENDS_ONLY,
            student__profile__friends=request.user
        )

        base_qs = base_qs.exclude(
            student__profile__privacy_level=UserProfile.PRIVACY_ONLY_ME
        ).filter(visibility_q)
    # For instructors, visibility is controlled by instructor_visibility field (already filtered above)

    # Also consider active PresenceSession and SignInRecord rows as "online" for status accuracy.
    active_sessions = PresenceSession.objects.filter(
        is_active=True
    ).select_related('room').order_by('-signed_in_at')
    active_session_by_user = {}
    for session in active_sessions:
        if session.user_id not in active_session_by_user:
            active_session_by_user[session.user_id] = session
    active_signins = _effective_active_signins_qs().select_related('room').order_by('-sign_in_time')
    active_signin_by_user = {}
    for record in active_signins:
        if record.student_id not in active_signin_by_user:
            active_signin_by_user[record.student_id] = record

    # Build always-visible online list from active records only.
    if selected_role == 'student':
        online_students = base_qs.filter(
            Q(student__presence_sessions__is_active=True)
            | Q(student__sign_in_records__sign_out_time__isnull=True)
        ).exclude(student=request.user).order_by('-last_seen').distinct()

        # Normalize to uniform objects for template consumption
        online_students = [
            {
                'user': p.student,
                'current_room': p.current_room,
                'is_online': p.is_online,
                'original_presence': p,
            }
            for p in online_students
        ]
    else:
        # Use PresenceSession for instructors - only show those with instructor_visibility = 'everyone'
        instructor_sessions = PresenceSession.objects.filter(
            is_active=True,
            user__instructor_profile__isnull=False,
            user__profile__instructor_visibility=UserProfile.INSTRUCTOR_VISIBILITY_EVERYONE
        ).select_related('user', 'room').order_by('-signed_in_at')

        online_students = []
        for session in instructor_sessions:
            if session.user == request.user:
                continue
            online_students.append({
                'user': session.user,
                'current_room': session.room,
                'is_online': True,
                'original_presence': None,
            })

    # Reconcile stale StudentPresence rows using active PresenceSession state.
    def _reconcile_status(presence_obj):
        active_session = active_session_by_user.get(presence_obj.student_id)
        active_signin = active_signin_by_user.get(presence_obj.student_id)
        resolved_online = bool(active_session or active_signin)
        presence_obj.resolved_online = resolved_online

        active_room = None
        if active_signin and active_signin.room:
            active_room = active_signin.room
        elif active_session and active_session.room:
            active_room = active_session.room

        # Outside department should not show stale previous room values.
        if active_room and active_room.name != 'Student Lounge':
            presence_obj.current_room = active_room
        else:
            presence_obj.current_room = None

    if query:
        # Search by username, full name, or student ID.
        if selected_role == 'student':
            # Students: base_qs already respects privacy rules.
            results = base_qs.filter(
                Q(student__username__icontains=query) |
                Q(student__first_name__icontains=query) |
                Q(student__last_name__icontains=query) |
                Q(student__profile__student_id_number__icontains=query)
            ).exclude(student=request.user).distinct()

            # partition into public vs custom (friends-only) lists for display
            public_results = []
            custom_results = []
            for presence in results:
                try:
                    level = presence.student.profile.privacy_level
                except Exception:
                    level = None
                if level == UserProfile.PRIVACY_PUBLIC:
                    public_results.append(presence)
                elif level == UserProfile.PRIVACY_FRIENDS_ONLY:
                    custom_results.append(presence)
            # reconcile statuses for both partitions
            for presence in public_results + custom_results:
                _reconcile_status(presence)
            results = None  # clear original to avoid confusion, use new lists
        else:
            # Instructors: Search directly in User and InstructorProfile tables
            # since instructors may not have StudentPresence records
            from django.shortcuts import get_object_or_404
            instructor_users = User.objects.filter(
                Q(username__icontains=query) |
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query),
                instructor_profile__isnull=False,
                profile__instructor_visibility=UserProfile.INSTRUCTOR_VISIBILITY_EVERYONE
            ).exclude(id=request.user.id).distinct()

            # Create/fetch presence objects for instructors for template compatibility
            public_results = []
            for user in instructor_users:
                try:
                    profile = user.profile
                except UserProfile.DoesNotExist:
                    profile = UserProfile.objects.create(user=user)
                
                # Try to get or create a StudentPresence for template compatibility
                try:
                    presence = StudentPresence.objects.get(student=user)
                except StudentPresence.DoesNotExist:
                    presence = StudentPresence(student=user, is_online=False)
                
                # Mark as instructor for template display
                presence.is_instructor = True
                public_results.append(presence)
            
            custom_results = []
            results = None
    else:
        # No query: keep results empty and show online list above.
        public_results = []
        custom_results = []
        results = None

    if results is not None:
        for row in results:
            _reconcile_status(row)
    if online_students is not None and selected_role == 'student':
        for row in online_students:
            # row is now a dict wrapper for data; reconcile actual StudentPresence for student role only
            if isinstance(row, dict) and row.get('original_presence'):
                _reconcile_status(row['original_presence'])

    context = {
        'query': query,
        'public_results': public_results,
        'custom_results': custom_results,
        'online_students': online_students,
        'selected_role': selected_role,
        'online_title': online_title,
    }

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        def _serialize_presence(presence_obj):
            user = getattr(presence_obj, 'student', None)
            profile = getattr(user, 'profile', None) if user else None
            resolved_online = getattr(presence_obj, 'resolved_online', None)
            is_online = bool(resolved_online) if resolved_online is not None else bool(getattr(presence_obj, 'is_online', False))
            current_room = getattr(presence_obj, 'current_room', None)
            profile_picture_url = None
            try:
                if profile and getattr(profile, 'profile_picture', None):
                    profile_picture_url = profile.profile_picture.url
            except Exception:
                profile_picture_url = None

            return {
                'username': getattr(user, 'username', ''),
                'full_name': (user.get_full_name() if user else '') or getattr(user, 'username', ''),
                'student_id_number': getattr(profile, 'student_id_number', '') or '-',
                'phone_number': getattr(profile, 'phone_number', '') or '-',
                'profile_picture_url': profile_picture_url,
                'is_online': is_online,
                'room_name': getattr(current_room, 'name', None),
            }

        def _serialize_online(row):
            if isinstance(row, dict):
                user = row.get('user')
                room = row.get('current_room')
                return {
                    'username': getattr(user, 'username', ''),
                    'room_name': getattr(room, 'name', None) if room else None,
                }

            user = getattr(row, 'student', None)
            room = getattr(row, 'current_room', None)
            return {
                'username': getattr(user, 'username', ''),
                'room_name': getattr(room, 'name', None) if room else None,
            }

        return JsonResponse({
            'success': True,
            'query': query,
            'selected_role': selected_role,
            'online_title': online_title,
            'online_students': [ _serialize_online(r) for r in (online_students or []) ],
            'public_results': [ _serialize_presence(p) for p in (public_results or []) ],
            'custom_results': [ _serialize_presence(p) for p in (custom_results or []) ],
        })
    
    return render(request, 'search.html', context)


@login_required(login_url='login')
def profile_view(request, username=None):
    """Display user profile with profile picture and information."""
    if username:
        # View another user's profile
        user = get_object_or_404(User, username=username)
        is_own_profile = user == request.user
    else:
        # View own profile
        user = request.user
        is_own_profile = True
    
    # Restrict admin/staff users from viewing profiles
    if user.is_staff or user.is_superuser:
        return redirect('admin:index')
    
    try:
        profile = user.profile  # type: ignore
    except UserProfile.DoesNotExist:
        # Don't auto-create UserProfile for staff/superuser accounts
        if user.is_staff or user.is_superuser:
            profile = None
        else:
            profile = UserProfile.objects.create(user=user)
    
    try:
        presence = user.studentpresence  # type: ignore
    except:
        presence = None

    # Determine if the profile belongs to an instructor and fetch instructor profile if present
    try:
        instructor_profile_obj = user.instructor_profile
        is_instructor = True
    except InstructorProfile.DoesNotExist:
        instructor_profile_obj = None
        # Also check if user is staff/superuser
        is_instructor = user.is_staff or user.is_superuser

    # If user has a presence record, check for an active SignInRecord. If there's no active sign-in,
    # clear the displayed current_room so templates can treat the user as "outside department".
    if presence:
        active_signin = SignInRecord.objects.filter(student=user, sign_out_time__isnull=True).exists()
        if not active_signin:
            presence.current_room = None
    
    if request.method == 'POST' and is_own_profile:
        # Handle admin-only clear operations
        if request.user.is_staff or request.user.is_superuser:
            wants_json = (
                request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                or (request.headers.get('Content-Type', '') or '').startswith('application/json')
            )
            
            post_data = request.POST
            if (request.headers.get('Content-Type', '') or '').startswith('application/json'):
                try:
                    post_data = json.loads(request.body or b'{}')
                except json.JSONDecodeError:
                    post_data = {}
            
            # Clear profile picture
            if 'clear_profile_picture' in post_data:
                if profile and profile.profile_picture:
                    profile.profile_picture.delete()
                    profile.save()
                if wants_json:
                    return JsonResponse({'success': True, 'message': 'Profile picture cleared.'})
                messages.success(request, '✓ Profile picture cleared.')
                return redirect(request.path)
            
            # Clear bio
            if 'clear_bio' in post_data:
                if profile:
                    profile.bio = ''
                    profile.save()
                if wants_json:
                    return JsonResponse({'success': True, 'message': 'Bio cleared.'})
                messages.success(request, '✓ Bio cleared.')
                return redirect(request.path)
        
        # Regular form processing
        # Staff users don't have UserProfiles, skip form processing
        if profile is None:
            return redirect(request.path)
            
        wants_json = (
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or (request.headers.get('Content-Type', '') or '').startswith('application/json')
        )

        post_data = request.POST
        if (request.headers.get('Content-Type', '') or '').startswith('application/json'):
            try:
                post_data = json.loads(request.body or b'{}')
            except json.JSONDecodeError:
                post_data = {}

        form = ProfileForm(post_data, instance=profile)
        if form.is_valid():
            # Update user fields
            user.first_name = form.cleaned_data.get('first_name', '')
            user.last_name = form.cleaned_data.get('last_name', '')
            user.email = form.cleaned_data.get('email', '')
            user.save()

            # Update profile
            form.save()

            message = 'Profile updated successfully.'
            if not wants_json:
                messages.success(request, f'✓ {message}')

            if wants_json:
                profile_picture_url = None
                try:
                    if profile.profile_picture:
                        profile_picture_url = profile.profile_picture.url
                except Exception:
                    profile_picture_url = None

                return JsonResponse({
                    'success': True,
                    'message': message,
                    'profile': {
                        'username': user.username,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'full_name': user.get_full_name() or user.username,
                        'email': user.email or '',
                        'student_id_number': profile.student_id_number or '',
                        'phone_number': profile.phone_number or '',
                        'bio': profile.bio or '',
                        'profile_picture_url': profile_picture_url,
                    }
                })

            return redirect(request.path)

        if wants_json:
            field_errors = {}
            for field_name, errors in form.errors.items():
                field_errors[field_name] = [str(e) for e in errors]
            return JsonResponse({
                'success': False,
                'message': 'Please correct the highlighted fields and try again.',
                'errors': field_errors,
            }, status=400)
    else:
        initial_data = {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
        }
        form = ProfileForm(instance=profile, initial=initial_data) if (is_own_profile and profile is not None) else None
    
    context = {
        'profile_user': user,
        'profile': profile,
        'presence': presence,
        'is_instructor': is_instructor,
        'instructor_profile_obj': instructor_profile_obj,
        'form': form,
        'is_own_profile': is_own_profile,
    }
    
    return render(request, 'profile.html', context)


@login_required(login_url='login')
@require_http_methods(["POST"])
def upload_profile_picture(request):
    """Upload and persist the authenticated user's profile picture."""
    wants_json = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or (request.headers.get('Content-Type', '') or '').startswith('application/json')
    )
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    upload = request.FILES.get('profile_picture')
    if not upload:
        if wants_json:
            return JsonResponse({'success': False, 'status': 'error', 'message': 'No file uploaded.'}, status=400)
        messages.error(request, 'No file uploaded.')
        return redirect(request.META.get('HTTP_REFERER', 'profile'))

    if upload.size > (5 * 1024 * 1024):
        if wants_json:
            return JsonResponse({'success': False, 'status': 'error', 'message': 'Image must be 5MB or less.'}, status=400)
        messages.error(request, 'Image must be 5MB or less.')
        return redirect(request.META.get('HTTP_REFERER', 'profile'))

    content_type = (upload.content_type or '').lower()
    if not content_type.startswith('image/'):
        if wants_json:
            return JsonResponse({'success': False, 'status': 'error', 'message': 'Invalid file type. Upload an image.'}, status=400)
        messages.error(request, 'Invalid file type. Upload an image.')
        return redirect(request.META.get('HTTP_REFERER', 'profile'))

    profile.profile_picture = upload
    profile.save()
    if wants_json:
        return JsonResponse({
            'success': True,
            'status': 'ok',
            'message': 'Profile picture updated.',
            'image_url': profile.profile_picture.url,
        })

    messages.success(request, 'Profile picture updated.')
    return redirect(request.META.get('HTTP_REFERER', 'profile'))


@login_required(login_url='login')
@require_http_methods(["POST"])
def privacy_update(request):
    """AJAX endpoint to update the logged-in user's privacy level and selected peers."""
    wants_json = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or (request.headers.get('Content-Type', '') or '').startswith('application/json')
    )
    payload = None
    if (request.headers.get('Content-Type', '') or '').startswith('application/json'):
        try:
            payload = json.loads(request.body or b'{}')
        except json.JSONDecodeError:
            payload = {}
    else:
        payload = request.POST

    try:
        profile, created = UserProfile.objects.get_or_create(user=request.user)
    except Exception:
        if wants_json:
            return JsonResponse({'success': False, 'status': 'error', 'message': 'Profile not found'}, status=400)
        messages.error(request, 'Profile not found.')
        return redirect(request.META.get('HTTP_REFERER', 'peer_search'))

    new_level = payload.get('privacy_level') if isinstance(payload, dict) else payload.get('privacy_level')
    valid_levels = {c[0] for c in UserProfile.PRIVACY_CHOICES}
    if new_level not in valid_levels:
        if wants_json:
            return JsonResponse({'success': False, 'status': 'error', 'message': 'Invalid privacy level'}, status=400)
        messages.error(request, 'Invalid privacy level.')
        return redirect(request.META.get('HTTP_REFERER', 'peer_search'))

    profile.privacy_level = new_level
    
    # Handle selected peers for FRIENDS_ONLY privacy
    if new_level == UserProfile.PRIVACY_FRIENDS_ONLY:
        selected_peer_ids = None
        if isinstance(payload, dict) and 'selected_peers' in payload:
            selected_peer_ids = payload.get('selected_peers')
        elif hasattr(payload, 'get') and payload.get('selected_peers'):
            selected_peers_json = payload.get('selected_peers')
            try:
                selected_peer_ids = json.loads(selected_peers_json) if isinstance(selected_peers_json, str) else selected_peers_json
            except json.JSONDecodeError:
                selected_peer_ids = None

        # Only overwrite the stored access list when the client explicitly sends it.
        if selected_peer_ids is not None:
            try:
                profile.friends.clear()
                for peer_id in (selected_peer_ids or []):
                    try:
                        peer_user = User.objects.get(id=peer_id)
                        profile.friends.add(peer_user)
                    except User.DoesNotExist:
                        continue
            except Exception:
                # Never block privacy updates due to friend list issues.
                pass
    
    profile.save()

    if wants_json:
        return JsonResponse({
            'success': True,
            'status': 'ok',
            'message': 'Location privacy updated.',
            'privacy_level': profile.privacy_level,
        })

    messages.success(request, 'Location privacy updated.')
    return redirect(request.META.get('HTTP_REFERER', 'peer_search'))


@login_required(login_url='login')
def instructor_privacy_update(request):
    """AJAX endpoint to update the logged-in instructor's visibility setting."""
    wants_json = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or (request.headers.get('Content-Type', '') or '').startswith('application/json')
    )
    if request.method != 'POST':
        if wants_json:
            return JsonResponse({'success': False, 'status': 'error', 'message': 'POST required'}, status=400)
        return redirect(request.META.get('HTTP_REFERER', 'profile'))
    
    try:
        profile, created = UserProfile.objects.get_or_create(user=request.user)
    except Exception:
        if wants_json:
            return JsonResponse({'success': False, 'status': 'error', 'message': 'Profile not found'}, status=400)
        messages.error(request, 'Profile not found.')
        return redirect(request.META.get('HTTP_REFERER', 'profile'))

    if (request.headers.get('Content-Type', '') or '').startswith('application/json'):
        try:
            payload = json.loads(request.body or b'{}')
        except json.JSONDecodeError:
            payload = {}
        new_visibility = payload.get('instructor_visibility')
    else:
        new_visibility = request.POST.get('instructor_visibility')

    valid_visibilities = {c[0] for c in UserProfile.INSTRUCTOR_VISIBILITY_CHOICES}
    if new_visibility not in valid_visibilities:
        if wants_json:
            return JsonResponse({'success': False, 'status': 'error', 'message': 'Invalid visibility setting'}, status=400)
        messages.error(request, 'Invalid visibility setting.')
        return redirect(request.META.get('HTTP_REFERER', 'profile'))

    profile.instructor_visibility = new_visibility
    profile.save()

    if wants_json:
        return JsonResponse({
            'success': True,
            'status': 'ok',
            'message': 'Location privacy updated.',
            'instructor_visibility': profile.instructor_visibility,
        })

    messages.success(request, 'Location privacy updated.')
    return redirect(request.META.get('HTTP_REFERER', 'profile'))


@login_required(login_url='login')
def search_peers_api(request):
    """
    API endpoint to search for users (students/instructors) by username.
    Used both by the user discovery page and by the privacy manager when adding allowed friends.
    
    Privacy rules are evaluated from the perspective of the account being
    queried (i.e. the user whose name is being searched):

    For Students:
    - PUBLIC: everyone can see the user.
    - FRIENDS_ONLY ("Custom"): only people explicitly added to that user's
      friends/access list may see them.
    - ONLY_ME: the user never appears in search results for anyone else.
    
    For Instructors:
    - instructor_visibility='everyone': searchable by all users
    - instructor_visibility='none': not searchable at all
    
    Users can be searched if their privacy allows it, regardless of online status.

    When invoked from the privacy manager the returned list is also filtered
    to remove any users that the searching account has already added (so you
    cannot add the same friend twice).
    """
    query = request.GET.get('q', '').strip()
    
    if len(query) < 1:
        return JsonResponse({'peers': [], 'results': []})
    
    # Build the query to find matching users - search all users except staff/superuser/self
    # This includes both students and instructors
    matching_users = User.objects.filter(
        Q(username__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query)
    ).exclude(id=request.user.id).exclude(is_staff=True).exclude(is_superuser=True).distinct()
    
    # Determine users already in the searcher's access list so we can hide them
    try:
        searcher_profile = UserProfile.objects.get(user=request.user)
        existing_ids = set(searcher_profile.friends.values_list('id', flat=True))
    except UserProfile.DoesNotExist:
        existing_ids = set()

    # Now filter by privacy rules at database level
    peers_list = []
    
    for user in matching_users[:50]:  # Check up to 50 matches
        # skip any user already in the access list
        if user.id in existing_ids:
            continue
        
        # Check if user is an instructor
        is_instructor = False
        try:
            user.instructor_profile
            is_instructor = True
        except InstructorProfile.DoesNotExist:
            is_instructor = False
        
        try:
            user_profile = user.profile
        except UserProfile.DoesNotExist:
            # Create profile if it doesn't exist
            user_profile = UserProfile.objects.create(user=user)
        
        # Handle instructor search with instructor_visibility
        if is_instructor:
            # For instructors, check instructor_visibility setting
            if user_profile.instructor_visibility == UserProfile.INSTRUCTOR_VISIBILITY_NONE:
                continue  # Instructor not searchable
            
            # Instructor is searchable (instructor_visibility='everyone')
            peers_list.append({
                'id': user.id,
                'username': user.username,
                'display_name': f"{user.first_name} {user.last_name}".strip() or user.username,
                'privacy': 'instructor'
            })
            continue
        
        # Handle student search with privacy_level
        # RULE 1: ONLY_ME - Never show in search results
        if user_profile.privacy_level == UserProfile.PRIVACY_ONLY_ME:
            continue
        
        # RULE 2: PUBLIC - Show to everyone
        if user_profile.privacy_level == UserProfile.PRIVACY_PUBLIC:
            peers_list.append({
                'id': user.id,
                'username': user.username,
                'display_name': f"{user.first_name} {user.last_name}".strip() or user.username,
                'privacy': 'public'
            })
            continue
        
        # RULE 3: FRIENDS_ONLY (Custom) - Show only if the searcher is allowed by them
        if user_profile.privacy_level == UserProfile.PRIVACY_FRIENDS_ONLY:
            # check whether the searching user has been granted access
            if request.user in user_profile.friends.all():
                peers_list.append({
                    'id': user.id,
                    'username': user.username,
                    'display_name': f"{user.first_name} {user.last_name}".strip() or user.username,
                    'privacy': 'custom'
                })
            # otherwise don't include them
            continue
    
    return JsonResponse({'peers': peers_list, 'results': peers_list})


@login_required(login_url='login')
def allowed_friends_api(request):
    """API endpoint to get list of friends with location access."""
    try:
        profile = UserProfile.objects.get(user=request.user)
        allowed_friends = profile.friends.all().values('id', 'username', 'first_name', 'last_name')
        friends_list = [
            {
                'id': friend['id'],
                'username': friend['username'],
                'display_name': f"{friend['first_name']} {friend['last_name']}".strip() or friend['username']
            }
            for friend in allowed_friends
        ]
        return JsonResponse({'success': True, 'status': 'ok', 'allowed_friends': friends_list})
    except UserProfile.DoesNotExist:
        return JsonResponse({'success': True, 'status': 'ok', 'allowed_friends': []})


@login_required(login_url='login')
@require_http_methods(["POST"])
def add_friend_api(request):
    """API endpoint to add a friend to location access list."""
    import json
    try:
        profile = UserProfile.objects.get(user=request.user)
        data = json.loads(request.body)
        friend_id = data.get('friend_id')
        
        if not friend_id:
            return JsonResponse({'success': False, 'status': 'error', 'message': 'Friend ID required'}, status=400)
        
        try:
            friend_user = User.objects.get(id=friend_id)
            profile.friends.add(friend_user)
            profile.save()
            return JsonResponse({'success': True, 'status': 'ok', 'message': f'Added {friend_user.username} to access list'})
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'status': 'error', 'message': 'User not found'}, status=404)
    except UserProfile.DoesNotExist:
        # Create profile if doesn't exist
        profile = UserProfile.objects.create(user=request.user)
        friend_id = json.loads(request.body).get('friend_id')
        try:
            friend_user = User.objects.get(id=friend_id)
            profile.friends.add(friend_user)
            return JsonResponse({'success': True, 'status': 'ok', 'message': f'Added {friend_user.username} to access list'})
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'status': 'error', 'message': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'status': 'error', 'message': str(e)}, status=400)


@login_required(login_url='login')
@require_http_methods(["POST"])
def remove_friend_api(request):
    """API endpoint to remove a friend from location access list."""
    import json
    try:
        profile = UserProfile.objects.get(user=request.user)
        data = json.loads(request.body)
        friend_id = data.get('friend_id')
        
        if not friend_id:
            return JsonResponse({'success': False, 'status': 'error', 'message': 'Friend ID required'}, status=400)
        
        try:
            friend_user = User.objects.get(id=friend_id)
            profile.friends.remove(friend_user)
            profile.save()
            return JsonResponse({'success': True, 'status': 'ok', 'message': f'Removed {friend_user.username} from access list'})
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'status': 'error', 'message': 'User not found'}, status=404)
    except UserProfile.DoesNotExist:
        return JsonResponse({'success': False, 'status': 'error', 'message': 'Profile not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'status': 'error', 'message': str(e)}, status=400)


@login_required(login_url='login')
def attendance_dashboard(request):
    """Display user's attendance dashboard with sign-ins, FRC, activity hours, and calendar."""
    try:
        presence = StudentPresence.objects.get(student=request.user)
    except StudentPresence.DoesNotExist:
        presence = None
    
    # Get sign-in records (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    sign_in_records = SignInRecord.objects.filter(
        student=request.user,
        sign_in_time__gte=thirty_days_ago
    ).order_by('-sign_in_time')[:20]
    
    # FRC attendance stats (current month)
    today = date.today()
    current_month_start = today.replace(day=1)
    frc_records = FlagRaisingCeremony.objects.filter(
        student=request.user,
        attendance_date__gte=current_month_start
    ).order_by('-attendance_date')
    
    frc_present_count = frc_records.filter(present=True).count()
    frc_total_count = frc_records.count()
    
    # Activity hours (current month)
    activity_hours = ActivityHour.objects.filter(
        student=request.user,
        sign_in_time__date__gte=current_month_start
    ).order_by('-sign_in_time')
    
    # Get active activity
    active_activity = ActivityHour.objects.filter(
        student=request.user,
        sign_out_time__isnull=True
    ).first()

    # Determine if the cleaning sign-in button should be enabled
    now = timezone.now().astimezone(tz('Asia/Manila'))
    is_wednesday = now.weekday() == 2  # Monday=0, Tuesday=1, Wednesday=2
    within_window = (now.hour == 13 and now.minute <= 15)  # 13:00 - 13:15
    can_sign_in_activity = is_wednesday and within_window and (active_activity is None)
    
    # Calculate total activity hours for current month
    total_activity_hours = 0
    for activity in activity_hours:
        duration = activity.duration_hours()
        if duration:
            total_activity_hours += duration
    
    # Overall stats
    total_sign_ins = SignInRecord.objects.filter(student=request.user).count()
    total_frc_present = FlagRaisingCeremony.objects.filter(student=request.user, present=True).count()

    # Additional summary metrics for dashboard cards
    completed_cleaning_sessions = ActivityHour.objects.filter(
        student=request.user,
        sign_out_time__isnull=False
    ).count()

    completed_lab_records = SignInRecord.objects.filter(
        student=request.user,
        sign_out_time__isnull=False
    )
    total_lab_minutes = 0
    for rec in completed_lab_records:
        duration = rec.duration_minutes()
        if duration:
            total_lab_minutes += int(duration)
    total_lab_hours = round(total_lab_minutes / 60, 1) if total_lab_minutes else 0

    # FRC streak: consecutive "present" records from most recent backward
    frc_streak = 0
    frc_history = FlagRaisingCeremony.objects.filter(
        student=request.user
    ).order_by('-attendance_date').values_list('present', flat=True)
    for was_present in frc_history:
        if was_present:
            frc_streak += 1
        else:
            break
    
    # Calculate FRC attendance percentage
    frc_attendance_percentage = 0
    if frc_total_count > 0:
        frc_attendance_percentage = round((frc_present_count / frc_total_count) * 100)
    
    # ===== CALENDAR LOGIC =====
    year = today.year
    month = today.month
    
    # Generate calendar for the month
    cal = calendar.monthcalendar(year, month)
    
    # Get all Mondays (weekday 0) and Wednesdays (weekday 2) in the month
    mondays = []
    wednesdays = []
    
    for day_num in range(1, calendar.monthrange(year, month)[1] + 1):
        current_date = date(year, month, day_num)
        if current_date.weekday() == 0:  # Monday
            mondays.append(current_date)
        elif current_date.weekday() == 2:  # Wednesday
            wednesdays.append(current_date)
    
    # Fetch FRC records for this month
    frc_records_for_cal = FlagRaisingCeremony.objects.filter(
        student=request.user,
        attendance_date__year=year,
        attendance_date__month=month
    ).values_list('attendance_date', 'present')
    frc_dict = {record[0]: record[1] for record in frc_records_for_cal}
    
    # Fetch Activity Hour records for this month
    activity_records_for_cal = ActivityHour.objects.filter(
        student=request.user,
        sign_in_time__year=year,
        sign_in_time__month=month
    ).values_list('sign_in_time__date', 'sign_out_time')
    activity_dict = {
        record[0]: {'sign_in': True, 'sign_out': record[1] is not None}
        for record in activity_records_for_cal
    }
    
    # Build calendar data with attendance status
    calendar_data = []
    for week in cal:
        week_data = []
        for day in week:
            if day == 0:
                week_data.append(None)
            else:
                current_date = date(year, month, day)
                day_info = {
                    'day': day,
                    'date': current_date,
                    'is_monday': current_date in mondays,
                    'is_wednesday': current_date in wednesdays,
                    'status': None,
                }
                
                # Monday: Check FRC attendance
                if current_date in mondays:
                    if current_date in frc_dict:
                        day_info['status'] = 'success' if frc_dict[current_date] else 'absent'
                    else:
                        day_info['status'] = 'absent'
                
                # Wednesday: Check Activity Hour
                elif current_date in wednesdays:
                    if current_date in activity_dict:
                        record = activity_dict[current_date]
                        if record['sign_in'] and record['sign_out']:
                            day_info['status'] = 'success'  # Green check
                        elif record['sign_in'] and not record['sign_out']:
                            day_info['status'] = 'partial'  # Red X
                        else:
                            day_info['status'] = 'absent'
                    else:
                        day_info['status'] = 'absent'
                
                week_data.append(day_info)
        calendar_data.append(week_data)
    
    # Calculate monthly stats
    total_scheduled = len(mondays) + len(wednesdays)
    attended_count = (
        sum(1 for d in mondays if d in frc_dict and frc_dict[d]) +
        sum(1 for d in wednesdays if d in activity_dict and activity_dict[d]['sign_out'])
    )
    partial_count = sum(1 for d in wednesdays if d in activity_dict and not activity_dict[d]['sign_out'])
    absent_count = total_scheduled - attended_count - partial_count
    
    context = {
        'presence': presence,
        'today': today,
        'sign_in_records': sign_in_records,
        'frc_records': frc_records,
        'frc_present_count': frc_present_count,
        'frc_total_count': frc_total_count,
        'frc_attendance_percentage': frc_attendance_percentage,
        'activity_hours': activity_hours,
        'active_activity': active_activity,
        'total_activity_hours': total_activity_hours,
        'total_lab_hours': total_lab_hours,
        'total_sign_ins': total_sign_ins,
        'total_frc_present': total_frc_present,
        'completed_cleaning_sessions': completed_cleaning_sessions,
        'frc_streak': frc_streak,
        'can_sign_in_activity': can_sign_in_activity,
        # Calendar data
        'calendar': calendar_data,
        'month_name': calendar.month_name[month],
        'year': year,
        'weekdays': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        'cal_stats': {
            'total_scheduled': total_scheduled,
            'attended': attended_count,
            'partial': partial_count,
            'absent': absent_count,
            'attendance_rate': round((attended_count / total_scheduled * 100) if total_scheduled > 0 else 0),
        }
    }
    
    return render(request, 'attendance_dashboard.html', context)


@login_required(login_url='login')
def activity_signin(request):
    """Sign in to cleaning activity at 1pm."""
    now = timezone.now().astimezone(tz('Asia/Manila'))
    today = now.date()

    # Only allow sign-in on Wednesday between 13:00 and 13:15.
    if not (now.weekday() == 2 and now.hour == 13 and now.minute <= 15):
        messages.error(request, 'Cleaning sign-in is only available on Wednesdays from 1:00 PM to 1:15 PM.')
        return redirect('attendance_dashboard')
    
    # Check if already signed in today
    existing = ActivityHour.objects.filter(
        student=request.user,
        sign_in_time__date=today,
        sign_out_time__isnull=True
    ).first()
    
    if existing:
        messages.warning(request, '✓ You are already signed in for cleaning today.')
        return redirect('attendance_dashboard')
    
    # Check if already completed cleaning for today
    completed = ActivityHour.objects.filter(
        student=request.user,
        sign_in_time__date=today,
        sign_out_time__isnull=False
    ).first()
    
    if completed:
        time_str = completed.sign_out_time.strftime("%H:%M") if completed.sign_out_time else "unknown"
        messages.info(request, f'✓ You already completed cleaning today at {time_str}.')
        return redirect('attendance_dashboard')
    
    # Create cleaning activity anchored to 1:00 PM local time.
    sign_in_time = now.replace(hour=13, minute=0, second=0, microsecond=0)
    
    ActivityHour.objects.create(
        student=request.user,
        sign_in_time=sign_in_time
    )
    
    messages.success(request, '✓ Signed in for cleaning at 1pm')
    return redirect('attendance_dashboard')


@login_required(login_url='login')
def activity_signout(request, activity_id=None):
    """Sign out from cleaning activity at 5pm (or earlier if forced by admin)."""
    now = timezone.now().astimezone(tz('Asia/Manila'))
    today = now.date()
    
    if activity_id:
        activity = get_object_or_404(ActivityHour, id=activity_id, student=request.user)
    else:
        # Get today's active cleaning activity
        activity = ActivityHour.objects.filter(
            student=request.user,
            sign_in_time__date=today,
            sign_out_time__isnull=True
        ).first()
    
    if not activity:
        messages.error(request, 'No active cleaning session found.')
        return redirect('attendance_dashboard')
    
    # Check if it's before 5pm (17:00)
    five_pm = now.replace(hour=17, minute=0, second=0, microsecond=0)
    
    if now < five_pm:
        # Return JSON response or render template with warning modal
        context = {
            'show_warning': True,
            'activity': activity,
            'time_remaining': (five_pm - now).total_seconds() / 60,  # minutes remaining
        }
        return render(request, 'attendance_dashboard.html', context)
    
    # After 5pm, allow sign-out
    sign_out_time = five_pm  # Use 5pm as the sign-out time
    activity.sign_out_time = sign_out_time
    activity.save()
    
    duration = activity.duration_hours()
    messages.success(request, f'✓ Signed out from cleaning ({duration}h)')
    return redirect('attendance_dashboard')


@login_required(login_url='login')
def admin_cleaning_manage(request):
    """Admin view to manage student cleaning sign-outs."""
    is_admin = request.user.is_staff or request.user.is_superuser
    try:
        instructor_profile = request.user.instructor_profile
        is_instructor_manager = True
    except InstructorProfile.DoesNotExist:
        instructor_profile = None
        is_instructor_manager = False

    if not (is_admin or is_instructor_manager):
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('home')
    
    now = timezone.now().astimezone(tz('Asia/Manila'))
    today = now.date()
    
    # Instructors can only manage their own section. Admins can manage all sections.
    if is_admin:
        active_cleanings = ActivityHour.objects.filter(
            sign_in_time__date=today,
            sign_out_time__isnull=True
        ).select_related('student').order_by('sign_in_time')

        completed_cleanings = ActivityHour.objects.filter(
            sign_in_time__date=today,
            sign_out_time__isnull=False
        ).select_related('student').order_by('-sign_out_time')
    else:
        section = instructor_profile.section if instructor_profile else None
        if not section:
            active_cleanings = ActivityHour.objects.none()
            completed_cleanings = ActivityHour.objects.none()
            messages.warning(request, 'No section assigned yet. Ask an administrator to assign your section.')
        else:
            active_cleanings = ActivityHour.objects.filter(
                sign_in_time__date=today,
                sign_out_time__isnull=True,
                student__studentpresence__section=section
            ).select_related('student').order_by('sign_in_time')

            completed_cleanings = ActivityHour.objects.filter(
                sign_in_time__date=today,
                sign_out_time__isnull=False,
                student__studentpresence__section=section
            ).select_related('student').order_by('-sign_out_time')
    
    context = {
        'active_cleanings': active_cleanings,
        'completed_cleanings': completed_cleanings,
        'today': today,
        'now': now,
        'can_manage_cleaning': True,
    }
    
    return render(request, 'admin_cleaning_manage.html', context)


@login_required(login_url='login')
@require_http_methods(["POST"])
def admin_force_signout(request, activity_id):
    """Admin/instructor forces a student to sign out early."""
    is_admin = request.user.is_staff or request.user.is_superuser
    try:
        instructor_profile = request.user.instructor_profile
        is_instructor_manager = True
    except InstructorProfile.DoesNotExist:
        instructor_profile = None
        is_instructor_manager = False

    if not (is_admin or is_instructor_manager):
        messages.error(request, 'You do not have permission.')
        return redirect('home')
    
    activity = get_object_or_404(ActivityHour, id=activity_id)

    # Instructors may force sign-out only for students in their assigned section.
    if (not is_admin) and is_instructor_manager:
        section = instructor_profile.section if instructor_profile else None
        student_presence = StudentPresence.objects.filter(student=activity.student).first()
        if not section or not student_presence or student_presence.section != section:
            messages.error(request, 'You can only force sign-out students in your assigned section.')
            return redirect('admin_cleaning_manage')
    
    if activity.sign_out_time:
        messages.warning(request, f'{activity.student.username} already signed out.')
        return redirect('admin_cleaning_manage')
    
    # Force sign-out at current time
    activity.sign_out_time = timezone.now()
    activity.save()
    
    duration = activity.duration_hours()
    messages.success(request, f'✓ Forced {activity.student.username} to sign out ({duration}h)')
    return redirect('admin_cleaning_manage')


@login_required(login_url='login')
def instructor_dashboard(request):
    """Dashboard for instructors to manage their students' FRC attendance."""
    # Check if user is an instructor or staff/superuser
    instructor_profile = None
    is_staff_user = request.user.is_staff or request.user.is_superuser
    
    if not is_staff_user:
        try:
            instructor_profile = request.user.instructor_profile
        except InstructorProfile.DoesNotExist:
            messages.error(request, 'You do not have instructor privileges.')
            return redirect('home')

    # Get all rooms for the dropdown
    all_rooms = Room.objects.all().order_by('name')

    # Handle room selection (only for regular instructors with profile)
    if request.method == 'POST' and 'room_id' in request.POST and instructor_profile:
        room_id = request.POST.get('room_id')
        if room_id:
            room = get_object_or_404(Room, id=room_id)
            instructor_profile.instructor_room = room
            instructor_profile.save()
            messages.success(request, f'Your active room has been set to {room.name}.')
        else:
            # Handle case where "None" or empty value is selected
            instructor_profile.instructor_room = None
            instructor_profile.save()
            messages.success(request, 'Your active room has been cleared.')
        return redirect('instructor_dashboard')
    
    # Get students in this instructor's section
    section = instructor_profile.section
    # exclude any user who is also an instructor, staff, or superuser (only real students)
    instructor_users = InstructorProfile.objects.values_list('user_id', flat=True)
    students = (StudentPresence.objects
                .filter(section=section)
                .exclude(student__id__in=instructor_users)
                .exclude(student__is_staff=True)  # exclude staff members as well
                .exclude(student__is_superuser=True)  # exclude superusers
                .exclude(student__username__iexact='admin')  # exclude legacy admin account
                .select_related('student'))

    
    # Get FRC records for today
    today = timezone.now().astimezone(tz('Asia/Manila')).date()
    frc_records = {}
    for student_presence in students:
        frc = FlagRaisingCeremony.objects.filter(
            student=student_presence.student,
            attendance_date=today
        ).first()
        frc_records[student_presence.student.id] = frc  # type: ignore
    
    # Check if user is on university network
    network_status = 'online' if is_on_university_wifi(request) else 'offline'

    # Get instructor's current presence info
    try:
        instructor_presence = StudentPresence.objects.get(student=request.user)
        # Check if instructor has an active sign-in
        has_active_signin = SignInRecord.objects.filter(
            student=request.user,
            sign_out_time__isnull=True
        ).exists()
        # If signed out, set current_room to None to show "Outside department"
        if not has_active_signin:
            instructor_presence.current_room = None
    except StudentPresence.DoesNotExist:
        instructor_presence = None

    # heatmap students in same room; always keep as queryset so `.count()` works
    heatmap_students = StudentPresence.objects.none()
    if instructor_presence and instructor_presence.current_room:
        heatmap_students = StudentPresence.objects.filter(
            current_room=instructor_presence.current_room,
            is_online=True
        ).select_related('student')

    # number of empty slots needed to fill the grid so it remains rectangular
    heatmap_padding = 0
    if students is not None:
        # students is a queryset; evaluate count once
        total_students = students.count()
        heatmap_padding = max(0, total_students - heatmap_students.count())

    # network override toggle
    if request.method == 'POST' and 'toggle_network_override' in request.POST:
        instructor_profile.allow_off_network = not instructor_profile.allow_off_network
        instructor_profile.save()
        status = 'enabled' if instructor_profile.allow_off_network else 'disabled'
        messages.success(request, f'Network override {status}.')
        return redirect('instructor_dashboard')

    # handle broadcast message creation
    if request.method == 'POST' and 'broadcast_message' in request.POST:
        msg = request.POST.get('broadcast_message','').strip()
        if msg and instructor_presence and instructor_presence.current_room:
            Broadcast.objects.create(room=instructor_presence.current_room, message=msg)
            messages.success(request, 'Broadcast sent to students in room.')
            return redirect('instructor_dashboard')

    # Get current time in Philippines timezone
    philippines_tz = tz('Asia/Manila')
    current_time_ph = timezone.now().astimezone(philippines_tz)

    # compute simple stats for FRC progress ring
    total_students = students.count()
    present_count = sum(1 for r in frc_records.values() if r and r.present)
    frc_percentage = 0
    if total_students:
        frac = present_count / total_students
        frc_percentage = 100 - int(frac * 100)  # offset for dasharray

    context = {
        'instructor_profile': instructor_profile,
        'section': section,
        'students': students,
        'frc_records': frc_records,
        'today': today,
        'network_status': network_status,
        'instructor_presence': instructor_presence,
        'current_time_ph': current_time_ph,
        'frc_percentage': frc_percentage,
        'heatmap_students': heatmap_students,
        'heatmap_padding': heatmap_padding,
        'all_rooms': all_rooms,
    }
    
    return render(request, 'instructor_dashboard.html', context)


@login_required(login_url='login')
@require_http_methods(["POST"])
def instructor_mark_frc(request, student_id):
    """Mark FRC attendance for a student."""
    # Check if user is an instructor
    try:
        instructor_profile = request.user.instructor_profile
    except InstructorProfile.DoesNotExist:
        messages.error(request, 'You do not have instructor privileges.')
        return redirect('home')
    
    student = get_object_or_404(User, id=student_id)
    att_value = request.POST.get('attended')
    today = timezone.now().astimezone(tz('Asia/Manila')).date()
    
    # Check if student is in instructor's section
    student_presence = StudentPresence.objects.filter(student=student).first()
    if not student_presence or student_presence.section != instructor_profile.section:
        messages.error(request, 'This student is not in your section.')
        return redirect('instructor_dashboard')
    
    # support toggle POST from card clicks
    if att_value == 'toggle':
        frc, created = FlagRaisingCeremony.objects.get_or_create(student=student, attendance_date=today)
        if not created:
            frc.present = not frc.present
        else:
            frc.present = True
        frc.save()
        status = 'present' if frc.present else 'absent'
        messages.success(request, f"Toggled {student.username} to {status} for FRC.")
        return redirect('instructor_dashboard')
    
    attended = att_value == 'yes'
    # Update or create FRC record
    frc, created = FlagRaisingCeremony.objects.update_or_create(
        student=student,
        attendance_date=today,
        defaults={'present': attended}
    )
    
    status = "attended ✓" if attended else "absent ✗"
    messages.success(request, f'{student.username} marked as {status}')
    return redirect('instructor_dashboard')


@login_required(login_url='login')
def instructor_reports(request):
    """Section-level instructor reporting with CSV export."""
    try:
        instructor_profile = request.user.instructor_profile
    except InstructorProfile.DoesNotExist:
        messages.error(request, 'You do not have instructor privileges.')
        return redirect('home')

    section = instructor_profile.section
    if not section:
        messages.warning(request, 'No section assigned yet. Ask an administrator to assign your section.')
        return redirect('instructor_dashboard')

    today = timezone.now().astimezone(tz('Asia/Manila')).date()
    default_start = today - timedelta(days=30)
    start_str = request.GET.get('start_date', default_start.strftime('%Y-%m-%d'))
    end_str = request.GET.get('end_date', today.strftime('%Y-%m-%d'))

    try:
        start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
    except ValueError:
        start_date = default_start
        end_date = today
        messages.warning(request, 'Invalid date format. Using last 30 days.')

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    ph_tz = tz('Asia/Manila')
    start_dt = ph_tz.localize(datetime.combine(start_date, datetime.min.time()))
    end_dt = ph_tz.localize(datetime.combine(end_date, datetime.max.time()))

    students = (User.objects
                .filter(studentpresence__section=section)
                .distinct()
                .order_by('last_name', 'first_name', 'username'))

    rows = []
    total_signins = 0
    total_frc_present = 0
    total_frc_absent = 0
    total_cleaning = 0
    total_cleaning_hours = 0.0

    for student in students:
        signins = SignInRecord.objects.filter(
            student=student, sign_in_time__gte=start_dt, sign_in_time__lte=end_dt
        ).count()
        frc_present = FlagRaisingCeremony.objects.filter(
            student=student, attendance_date__gte=start_date, attendance_date__lte=end_date, present=True
        ).count()
        frc_absent = FlagRaisingCeremony.objects.filter(
            student=student, attendance_date__gte=start_date, attendance_date__lte=end_date, present=False
        ).count()

        cleaning_qs = ActivityHour.objects.filter(
            student=student, sign_in_time__gte=start_dt, sign_in_time__lte=end_dt
        )
        cleaning_sessions = cleaning_qs.count()
        cleaning_hours = 0.0
        for act in cleaning_qs:
            if act.sign_out_time:
                delta = act.sign_out_time - act.sign_in_time
                cleaning_hours += max(0.0, delta.total_seconds() / 3600.0)

        total_signins += signins
        total_frc_present += frc_present
        total_frc_absent += frc_absent
        total_cleaning += cleaning_sessions
        total_cleaning_hours += cleaning_hours

        rows.append({
            'student_name': student.get_full_name() or student.username,
            'username': student.username,
            'signins': signins,
            'frc_present': frc_present,
            'frc_absent': frc_absent,
            'cleaning_sessions': cleaning_sessions,
            'cleaning_hours': round(cleaning_hours, 1),
        })

    if request.GET.get('export') == 'csv':
        import csv
        from django.http import HttpResponse
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = (
            f'attachment; filename=\"instructor_report_{section}_{start_date}_{end_date}.csv\"'
        )
        writer = csv.writer(response)
        writer.writerow([
            'Section', 'Date From', 'Date To', 'Student Name', 'Username',
            'Room Sign-ins', 'FRC Present', 'FRC Absent', 'Cleaning Sessions', 'Cleaning Hours'
        ])
        for row in rows:
            writer.writerow([
                str(section), start_date, end_date, row['student_name'], row['username'],
                row['signins'], row['frc_present'], row['frc_absent'],
                row['cleaning_sessions'], row['cleaning_hours'],
            ])
        return response

    context = {
        'instructor_profile': instructor_profile,
        'section': section,
        'start_date': start_date,
        'end_date': end_date,
        'rows': rows,
        'total_students': len(rows),
        'total_signins': total_signins,
        'total_frc_present': total_frc_present,
        'total_frc_absent': total_frc_absent,
        'total_cleaning': total_cleaning,
        'total_cleaning_hours': round(total_cleaning_hours, 1),
    }
    return render(request, 'instructor_reports.html', context)


@login_required(login_url='login')
def instructor_manage_signout(request):
    """Instructor view to adjust student sign-out times for cleaning activity."""
    # Check if user is an instructor or staff/superuser
    instructor_profile = None
    is_staff_user = request.user.is_staff or request.user.is_superuser
    
    if not is_staff_user:
        try:
            instructor_profile = request.user.instructor_profile
        except InstructorProfile.DoesNotExist:
            messages.error(request, 'You do not have instructor privileges.')
            return redirect('home')
    
    section = instructor_profile.section if instructor_profile else None
    today = timezone.now().astimezone(tz('Asia/Manila')).date()
    recent_cutoff = today - timedelta(days=7)

    if not section and not is_staff_user:
        activities = ActivityHour.objects.none()
        recent_activities = ActivityHour.objects.none()
        messages.warning(request, 'No section assigned yet. Ask an administrator to assign your section.')
    else:
        # Primary panel: today's sessions (all if staff, section-filtered if instructor)
        if is_staff_user:
            activities = ActivityHour.objects.filter(
                sign_in_time__date=today
            ).select_related('student').order_by('-sign_in_time')
        else:
            activities = ActivityHour.objects.filter(
                student__studentpresence__section=section,
                sign_in_time__date=today
            ).select_related('student').order_by('-sign_in_time')

        # Secondary panel: last 7 days (including today) so instructors can still adjust records
        if is_staff_user:
            recent_activities = ActivityHour.objects.filter(
                sign_in_time__date__gte=recent_cutoff
            ).select_related('student').order_by('-sign_in_time')[:100]
        else:
            recent_activities = ActivityHour.objects.filter(
                student__studentpresence__section=section,
                sign_in_time__date__gte=recent_cutoff
            ).select_related('student').order_by('-sign_in_time')[:100]

    # compute a simple progress percentage for each activity (assuming 2h required)
    now = timezone.now()
    for act in list(activities) + list(recent_activities):
        if act.sign_out_time:
            act.progress = 100
        else:
            elapsed = now - act.sign_in_time
            minutes = elapsed.total_seconds() / 60
            act.progress = max(0, min(100, int((minutes / 120) * 100)))
    
    # Check if user is on university network
    network_status = 'online' if is_on_university_wifi(request) else 'offline'
    
    context = {
        'instructor_profile': instructor_profile,
        'section': section,
        'activities': activities,
        'recent_activities': recent_activities,
        'today': today,
        'network_status': network_status,
    }
    
    return render(request, 'instructor_manage_signout.html', context)


@login_required(login_url='login')
@require_http_methods(["POST"])
def instructor_adjust_signout(request, activity_id):
    """Instructor adjusts a student's sign-out time."""
    # Check if user is an instructor
    try:
        instructor_profile = request.user.instructor_profile
    except InstructorProfile.DoesNotExist:
        messages.error(request, 'You do not have instructor privileges.')
        return redirect('home')
    
    activity = get_object_or_404(ActivityHour, id=activity_id)
    
    # Check if student is in instructor's section
    student_presence = StudentPresence.objects.filter(student=activity.student).first()
    if not student_presence or student_presence.section != instructor_profile.section:
        messages.error(request, 'This student is not in your section.')
        return redirect('instructor_manage_signout')
    
    # Get new sign-out time from request
    signout_time_str = request.POST.get('signout_time')
    signout_time_str_formatted = request.POST.get('signout_time_formatted')
    
    try:
        if signout_time_str:
            # Parse the time (format: "HH:MM")
            hours, minutes = map(int, signout_time_str.split(':'))
            sign_out_time = activity.sign_in_time.replace(hour=hours, minute=minutes, second=0, microsecond=0)
        else:
            sign_out_time = timezone.now()
        
        activity.sign_out_time = sign_out_time
        activity.save()
        
        duration = activity.duration_hours()
        messages.success(request, f'✓ Updated {activity.student.username}\'s sign-out time to {sign_out_time.strftime("%H:%M")} ({duration}h)')
    except ValueError:
        messages.error(request, 'Invalid time format. Please use HH:MM')
    
    return redirect('instructor_manage_signout')


# ============================================================================
# CIS-Prox: Network-Authenticated Presence & Peer Discovery Views
# ============================================================================

@login_required(login_url='login')
def presence_signin(request):
    """
    CIS-Prox Sign-In: Verify campus network and create a presence session.
    Only allows sign-in when user is on campus Wi-Fi.
    """
    wants_json = (request.headers.get('Content-Type', '') or '').startswith('application/json') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if not is_on_university_wifi(request):
        if not wants_json:
            messages.error(request, '⚠ You must be connected to campus Wi-Fi to sign in.')
        if wants_json:
            return JsonResponse({'success': False, 'message': 'You must be connected to campus Wi-Fi to sign in.'}, status=403)
        return redirect('home')
    
    if request.method == 'POST':
        if wants_json:
            try:
                payload = json.loads(request.body or b'{}')
            except json.JSONDecodeError:
                payload = {}
            room_id = payload.get('room') or payload.get('room_id')
        else:
            room_id = request.POST.get('room')
        
        if not room_id:
            if not wants_json:
                messages.error(request, 'Please select a room.')
            if wants_json:
                return JsonResponse({'success': False, 'message': 'Please select a room.'}, status=400)
            return redirect('presence_signin')
        
        try:
            room = Room.objects.get(id=room_id)
        except Room.DoesNotExist:
            if not wants_json:
                messages.error(request, 'Invalid room selected.')
            if wants_json:
                return JsonResponse({'success': False, 'message': 'Invalid room selected.'}, status=404)
            return redirect('presence_signin')
        
        # Get client IP
        client_ip = get_client_ip(request)
        
        # Check if user already has an active session
        active_session = PresenceSession.objects.filter(
            user=request.user,
            is_active=True
        ).first()
        
        if active_session:
            if not wants_json:
                messages.warning(request, f'You already have an active session in {active_session.room.name}. Please sign out first.')
            if wants_json:
                return JsonResponse({
                    'success': False,
                    'message': f'You already have an active session in {active_session.room.name}. Please sign out first.',
                }, status=409)
            return redirect('presence_signin')
        
        # Create new presence session
        session = PresenceSession.objects.create(
            user=request.user,
            room=room,
            ip_address=client_ip,
            is_verified=True,
            is_active=True
        )

        # Sync StudentPresence used by Find Peers.
        presence, _ = StudentPresence.objects.get_or_create(student=request.user)
        presence.current_room = room
        presence.is_online = True
        presence.save()

        # Log laboratory ENTRY immediately for history visibility.
        try:
            is_instructor_user = hasattr(request.user, 'instructor_profile')
        except Exception:
            is_instructor_user = False

        if (not is_instructor_user) and _is_laboratory_room(room):
            try:
                LaboratoryHistory.objects.create(
                    student=request.user,
                    room=room,
                    duration_minutes=0
                )
            except Exception:
                # Keep sign-in successful even if logging fails.
                pass
        
        message = f'✓ Signed in to {room.name}. Your location is now visible to peers.'
        if not wants_json:
            messages.success(request, message)
        if wants_json:
            return JsonResponse({
                'success': True,
                'message': message,
                'session': {
                    'room_id': room.id,
                    'room_name': room.name,
                    'signed_in_at': session.signed_in_at.isoformat(),
                    'signed_in_at_display': timezone.localtime(session.signed_in_at).strftime('%b %d, %Y %I:%M %p'),
                    'duration_minutes': 0,
                },
            })
        return redirect('presence_dashboard')
    
    # GET request - show room selection form
    try:
        request.user.instructor_profile
        is_instructor = True
    except InstructorProfile.DoesNotExist:
        is_instructor = False

    # Filter rooms: 5 lectures, 2 labs (Lab-1 & ORC), 1 student lounge
    lecture_keywords = ['Classroom', 'Lecture', 'Room 1', 'Room 2', 'Room 3', 'Room 4 (Classroom 4)', 'Room 5']
    lab_names = ['Lab-1 (Computer Lab 1)', 'ORC']
    lounge_keywords = ['Lounge', 'Student Lounge']
    
    room_names = lecture_keywords + lab_names + lounge_keywords
    rooms = Room.objects.filter(name__in=room_names).order_by('name')
    
    # highlight a card if user somehow has active session
    active_room_id = None
    existing = PresenceSession.objects.filter(user=request.user, is_active=True).first()
    if existing:
        active_room_id = existing.room.id

    context = {
        'rooms': rooms,
        'is_on_campus': is_on_university_wifi(request),
        'active_room_id': active_room_id,
    }
    return render(request, 'presence_signin.html', context)


@login_required(login_url='login')
def presence_signout(request):
    """
    CIS-Prox Sign-Out: End the active presence session.
    """
    wants_json = (request.headers.get('Content-Type', '') or '').startswith('application/json') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    # Find active session
    active_session = PresenceSession.objects.filter(
        user=request.user,
        is_active=True
    ).first()
    
    if not active_session:
        if not wants_json:
            messages.warning(request, 'You do not have an active session.')
        if wants_json:
            return JsonResponse({'success': False, 'message': 'You do not have an active session.'}, status=404)
        return redirect('presence_dashboard')
    
    if request.method == 'POST':
        room_name = active_session.room.name if active_session.room else "Unknown"
        duration = active_session.duration_minutes()
        
        active_session.mark_signed_out()

        # Sync StudentPresence used by Find Peers.
        try:
            presence = StudentPresence.objects.get(student=request.user)
            presence.is_online = False
            presence.current_room = None
            presence.save()
        except StudentPresence.DoesNotExist:
            pass
        
        message = f'✓ Signed out from {room_name}. Session duration: {duration} minutes.'
        if not wants_json:
            messages.success(request, message)
        if wants_json:
            return JsonResponse({'success': True, 'message': message, 'signed_out': True})
        return redirect('presence_dashboard')
    
    # GET request - confirm sign-out
    context = {
        'session': active_session,
    }
    return render(request, 'presence_signout.html', context)


@login_required(login_url='login')
def presence_search(request):
    """
    CIS-Prox Peer Discovery: Search for classmates' real-time locations.
    Returns active sessions for searched users with privacy controls applied.
    
    Privacy Rules:
    - PUBLIC: User appears to everyone
    - CUSTOM (FRIENDS_ONLY): User only appears to people who have been added to their friends list
    - ONLY_ME: User never appears in search results for anyone else
    """
    query = request.GET.get('q', '').strip()
    role = request.GET.get('role', 'student').lower().strip()
    if role not in ['student', 'instructor']:
        role = 'student'

    logger.debug('presence_search: role=%s query=%s user=%s', role, query, request.user.username)

    results = []
    error = None
    
    if query:
        if len(query) < 2:
            error = "Please enter at least 2 characters."
        else:
            # Get the searching user's section for classmate verification
            try:
                searcher_presence = StudentPresence.objects.get(student=request.user)
                searcher_section = searcher_presence.section
            except StudentPresence.DoesNotExist:
                # If searcher has no section, they can only see PUBLIC users
                searcher_section = None
            
            # Search for users by username or first/last name
            from django.db.models import Q

            # role-based filter logic for student/instructor
            if role == 'instructor':
                users = User.objects.filter(
                    Q(username__icontains=query) |
                    Q(first_name__icontains=query) |
                    Q(last_name__icontains=query),
                    instructor_profile__isnull=False
                ).exclude(id=request.user.id)
            else:
                users = User.objects.filter(
                    Q(username__icontains=query) |
                    Q(first_name__icontains=query) |
                    Q(last_name__icontains=query),
                    instructor_profile__isnull=True
                ).exclude(id=request.user.id)
            
            # Get active sessions for these users while respecting privacy
            for user in users:
                try:
                    user_profile = user.profile
                except UserProfile.DoesNotExist:
                    continue

                user_presence = None
                try:
                    user_presence = user.studentpresence
                except StudentPresence.DoesNotExist:
                    user_presence = None

                # debug what's stored for this user (useful for instructor detection)
                logger.debug(
                    'presence_search user=%s instructor=%s student_presence=%s privacy=%s',
                    user.username,
                    hasattr(user, 'instructor_profile'),
                    bool(user_presence),
                    user_profile.privacy_level,
                )

                # RULE 1: ONLY_ME - Never show in search results
                if user_profile.privacy_level == UserProfile.PRIVACY_ONLY_ME:
                    continue

                # RULE 2: PUBLIC - Show to everyone
                if user_profile.privacy_level == UserProfile.PRIVACY_PUBLIC:
                    session = PresenceSession.objects.filter(
                        user=user,
                        is_active=True,
                        is_verified=True
                    ).first()

                    if session:
                        results.append({
                            'user': user,
                            'room': session.room,
                            'signed_in_at': session.signed_in_at,
                            'duration': session.duration_minutes(),
                            'role_label': 'Instructor' if hasattr(user, 'instructor_profile') else 'Student',
                        })
                    continue

                # RULE 3: CUSTOM (FRIENDS_ONLY) - Show only to people on their access list
                if user_profile.privacy_level == UserProfile.PRIVACY_FRIENDS_ONLY:
                    if request.user in user_profile.friends.all():
                        session = PresenceSession.objects.filter(
                            user=user,
                            is_active=True,
                            is_verified=True
                        ).first()

                        if session:
                            results.append({
                                'user': user,
                                'room': session.room,
                                'signed_in_at': session.signed_in_at,
                                'duration': session.duration_minutes(),
                                'role_label': 'Instructor' if hasattr(user, 'instructor_profile') else 'Student',
                            })
                    continue
            
            if not results and len(query) >= 2:
                role_label = 'Instructors' if role == 'instructor' else 'Students'
                error = f"No {role_label.lower()} found matching '{query}'. Please try a different search term."
    
    context = {
        'query': query,
        'role': role,
        'selected_role': role.capitalize(),
        'results': results,
        'error': error,
    }

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        serialized_results = []
        for r in results:
            user = r.get('user')
            room = r.get('room')
            signed_in_at = r.get('signed_in_at')
            profile_picture_url = None
            try:
                if user and hasattr(user, 'profile') and user.profile.profile_picture:
                    profile_picture_url = user.profile.profile_picture.url
            except Exception:
                profile_picture_url = None

            serialized_results.append({
                'username': getattr(user, 'username', ''),
                'first_name': getattr(user, 'first_name', ''),
                'last_name': getattr(user, 'last_name', ''),
                'full_name': (user.get_full_name() if user else '') or getattr(user, 'username', ''),
                'role_label': r.get('role_label'),
                'profile_picture_url': profile_picture_url,
                'room_name': getattr(room, 'name', None) if room else None,
                'duration_minutes': r.get('duration'),
                'signed_in_at': signed_in_at.isoformat() if signed_in_at else None,
                'signed_in_at_display': timezone.localtime(signed_in_at).strftime('%I:%M %p') if signed_in_at else '',
            })

        if query and len(query) < 2:
            return JsonResponse({
                'success': False,
                'message': error or 'Please enter at least 2 characters.',
                'query': query,
                'role': role,
                'results': [],
            }, status=400)

        return JsonResponse({
            'success': True,
            'query': query,
            'role': role,
            'results': serialized_results,
            'message': error or '',
        })
    return render(request, 'presence_search.html', context)


@login_required(login_url='login')
def presence_dashboard(request):
    """
    CIS-Prox Dashboard: Personal attendance & session tracking.
    Shows user's active session, absence counts, and session history.
    """
    # Active session
    active_session = PresenceSession.objects.filter(
        user=request.user,
        is_active=True
    ).first()
    
    # Session history (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    session_history = PresenceSession.objects.filter(
        user=request.user,
        signed_in_at__gte=thirty_days_ago
    ).order_by('-signed_in_at')[:20]
    
    # FRC absences
    frc_total = FlagRaisingCeremony.objects.filter(student=request.user).count()
    frc_absent = FlagRaisingCeremony.objects.filter(
        student=request.user,
        present=False
    ).count()
    
    # Activity Hour sessions
    activity_hours_sessions = ActivityHour.objects.filter(
        student=request.user
    ).order_by('-sign_in_time')[:10]
    
    total_activity_hours = ActivityHour.objects.filter(
        student=request.user,
        sign_out_time__isnull=False
    ).aggregate(total=Sum('sign_out_time', default=0))
    
    is_on_campus = is_on_university_wifi(request)

    # Provide room list for AJAX sign-in UX on the dashboard (keeps non-JS fallback too).
    lecture_keywords = ['Classroom', 'Lecture', 'Room 1', 'Room 2', 'Room 3', 'Room 4 (Classroom 4)', 'Room 5']
    lab_names = ['Lab-1 (Computer Lab 1)', 'ORC']
    lounge_keywords = ['Lounge', 'Student Lounge']
    room_names = lecture_keywords + lab_names + lounge_keywords
    rooms = Room.objects.filter(name__in=room_names).order_by('name') if is_on_campus else Room.objects.none()

    context = {
        'active_session': active_session,
        'session_history': session_history,
        'frc_total': frc_total,
        'frc_absent': frc_absent,
        'activity_hours': activity_hours_sessions,
        'is_on_campus': is_on_campus,
        'rooms': rooms,
    }
    return render(request, 'presence_dashboard.html', context)


@login_required
def laboratory_history(request):
    """
    Display Laboratory History - instructor-only view for automatic exit tracking.
    Shows when students exited labs and how long they spent there.
    """
    try:
        is_instructor = hasattr(request.user, 'instructor_profile') or request.user.is_staff
    except Exception:
        is_instructor = False

    if not request.user.is_authenticated or not is_instructor:
        from django.contrib import messages
        messages.error(request, 'Access denied — laboratory history is for instructors only.')
        return redirect('dashboard')

    try:
        instructor_profile = request.user.instructor_profile
    except InstructorProfile.DoesNotExist:
        instructor_profile = None

    lab_rows = []
    total = 0
    try:
        lab_room_filter = Q(room__name__icontains='lab') | Q(room__name__icontains='orc')
        qs = (
            SignInRecord.objects.select_related('student', 'room')
            .filter(lab_room_filter)
            .order_by('-sign_in_time')
        )
        total = qs.count()

        for r in qs:
            section_name = ''
            try:
                sp = r.student.studentpresence
                if sp and sp.section:
                    section_name = str(sp.section)
            except Exception:
                section_name = ''

            student_id_number = ''
            try:
                profile = r.student.profile
                if profile and profile.student_id_number:
                    student_id_number = profile.student_id_number
            except Exception:
                student_id_number = ''

            duration_minutes = (
                r.duration_minutes()
                if r.sign_out_time
                else int((timezone.now() - r.sign_in_time).total_seconds() / 60)
            )
            duration_hours = int(duration_minutes // 60) if duration_minutes else 0
            duration_minutes_remainder = int(duration_minutes % 60) if duration_minutes else 0

            lab_rows.append({
                'student': r.student,
                'student_username': r.student.username,
                'student_full_name': r.student.get_full_name() or r.student.username,
                'section_name': section_name,
                'student_id_number': student_id_number,
                'room_name': r.room.name if r.room else 'Unknown',
                'entrance_time': r.sign_in_time,
                'exit_time': r.sign_out_time,
                'duration_minutes': duration_minutes,
                'duration_hours': duration_hours,
                'duration_minutes_remainder': duration_minutes_remainder,
            })
    except Exception:
        pass

    if request.GET.get('export') == 'csv':
        import csv
        from django.http import HttpResponse
        resp = HttpResponse(content_type='text/csv')
        resp['Content-Disposition'] = 'attachment; filename="lab_history.csv"'
        writer = csv.writer(resp)
        writer.writerow([
            'Username', 'Full Name', 'Section', 'Student ID',
            'Room', 'Entrance', 'Exit', 'Duration(min)'
        ])
        for row in lab_rows:
            writer.writerow([
                row.get('student_username', ''),
                row.get('student_full_name', row.get('student', '')),
                row.get('section_name', ''),
                row.get('student_id_number', ''),
                row.get('room_name', row.get('room', '')),
                row.get('entrance_time', ''),
                row.get('exit_time', ''),
                row.get('duration_minutes', row.get('duration', '')),
            ])
        return resp

    selected_date = None
    date_param = request.GET.get('date')
    if date_param:
        try:
            selected_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            selected_date = None

    from collections import defaultdict
    philippines_tz = tz('Asia/Manila')
    groups = defaultdict(list)
    for r in lab_rows:
        dt = r.get('entrance_time') or r.get('exit_time')
        if not dt:
            continue
        try:
            date_key = dt.astimezone(philippines_tz).date() if hasattr(dt, 'astimezone') else dt.date()
        except Exception:
            date_key = dt.date()
        groups[date_key].append(r)

    if groups and not selected_date:
        selected_date = max(groups.keys())
    if not selected_date:
        selected_date = timezone.now().date()

    selected_day_records = sorted(
        groups.get(selected_date, []),
        key=lambda x: x.get('exit_time') or x.get('entrance_time'),
        reverse=True,
    )
    selected_day_count = len(selected_day_records)

    month_param = request.GET.get('month')
    if month_param:
        try:
            view_month = datetime.strptime(month_param, '%Y-%m').date().replace(day=1)
        except ValueError:
            view_month = selected_date.replace(day=1)
    else:
        view_month = selected_date.replace(day=1)

    calendar_weeks = []
    for week in calendar.Calendar(firstweekday=6).monthdatescalendar(view_month.year, view_month.month):
        week_cells = []
        for day in week:
            week_cells.append({
                'day': day.day,
                'date': day,
                'in_month': day.month == view_month.month,
                'is_selected': day == selected_date,
                'has_records': day in groups,
                'url': f"{request.path}?date={day.strftime('%Y-%m-%d')}&month={view_month.strftime('%Y-%m')}",
            })
        calendar_weeks.append(week_cells)

    prev_month = (view_month.replace(day=1) - timedelta(days=1)).replace(day=1)
    next_month = (view_month + timedelta(days=31)).replace(day=1)
    week_labels = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    selected_date_display = selected_date.strftime('%B %d, %Y')
    calendar_url_base = request.path

    context = {
        'instructor_profile': instructor_profile,
        'total_exits': total,
        'calendar_weeks': calendar_weeks,
        'week_labels': week_labels,
        'view_month': view_month,
        'prev_month': prev_month.strftime('%Y-%m'),
        'next_month': next_month.strftime('%Y-%m'),
        'selected_date': selected_date,
        'selected_date_display': selected_date_display,
        'selected_day_records': selected_day_records,
        'selected_day_count': selected_day_count,
        'calendar_url_base': calendar_url_base,
    }
    return render(request, 'laboratory_history.html', context)


# ============ INSTRUCTOR ADMIN FEATURES ============

@login_required(login_url='login')
def instructor_admin(request):
    """
    Professional instructor administration panel for managing students and rooms.
    ONLY INSTRUCTORS can access this feature.
    """
    # Check if user is an instructor or staff/superuser
    instructor_profile = None
    is_staff_user = request.user.is_staff or request.user.is_superuser
    
    if not is_staff_user:
        try:
            instructor_profile = request.user.instructor_profile
        except InstructorProfile.DoesNotExist:
            messages.error(request, 'Access Denied: You do not have instructor privileges.')
            return redirect('home')
    
    section = instructor_profile.section if instructor_profile else None
    
    # Get all rooms in the system
    all_rooms = Room.objects.all().order_by('name')
    
    # Get students in this instructor's section
    instructor_users = InstructorProfile.objects.values_list('user_id', flat=True)
    students = (StudentPresence.objects
                .filter(section=section)
                .exclude(student__id__in=instructor_users)
                .exclude(student__is_staff=True)
                .exclude(student__is_superuser=True)
                .exclude(student__username__iexact='admin')
                .select_related('student', 'student__profile')
                .order_by('student__first_name', 'student__last_name'))
    
    if not section:
        students = StudentPresence.objects.none()
        messages.warning(request, 'No section assigned. Contact administrator to assign your section.')
    
    # Handle room addition
    if request.method == 'POST' and 'add_room' in request.POST:
        room_name = request.POST.get('room_name', '').strip()
        room_description = request.POST.get('room_description', '').strip()
        
        if room_name:
            if Room.objects.filter(name__iexact=room_name).exists():
                messages.warning(request, f'Room "{room_name}" already exists.')
            else:
                new_room = Room.objects.create(
                    name=room_name,
                    description=room_description
                )
                messages.success(request, f'✓ Room "{new_room.name}" created successfully.')
                return redirect('instructor_admin')
        else:
            messages.error(request, 'Room name is required.')
    
    # Handle room deletion
    if request.method == 'POST' and 'delete_room' in request.POST:
        room_id = request.POST.get('delete_room')
        try:
            room = Room.objects.get(id=room_id)
            room_name = room.name
            room.delete()
            messages.success(request, f'✓ Room "{room_name}" deleted successfully.')
            return redirect('instructor_admin')
        except Room.DoesNotExist:
            messages.error(request, 'Room not found.')
    
    # Handle student account status check
    accounts_created = []
    accounts_pending = []
    
    for student_presence in students:
        student = student_presence.student
        try:
            profile = student.profile
            has_account = True
            student_id = profile.student_id_number or 'Not set'
        except UserProfile.DoesNotExist:
            has_account = False
            student_id = 'Not set'
        
        student_data = {
            'id': student.id,
            'username': student.username,
            'full_name': student.get_full_name() or student.username,
            'email': student.email or 'No email set',
            'student_id': student_id,
            'has_account': has_account,
            'presence': student_presence,
        }
        
        if has_account:
            accounts_created.append(student_data)
        else:
            accounts_pending.append(student_data)
    
    # Check if user is on university network
    network_status = 'online' if is_on_university_wifi(request) else 'offline'
    
    # Get instructor's current presence info
    try:
        instructor_presence = StudentPresence.objects.get(student=request.user)
    except StudentPresence.DoesNotExist:
        instructor_presence = None
    
    context = {
        'instructor_profile': instructor_profile,
        'section': section,
        'all_rooms': all_rooms,
        'accounts_created': accounts_created,
        'accounts_pending': accounts_pending,
        'total_students': len(accounts_created) + len(accounts_pending),
        'network_status': network_status,
        'instructor_presence': instructor_presence,
    }
    
    return render(request, 'instructor_admin.html', context)


@login_required(login_url='login')
def instructor_admin_student_detail(request, student_id):
    """
    Display detailed student information for instructor management.
    ONLY INSTRUCTORS can access this feature.
    """
    # Check if user is an instructor or staff/superuser
    instructor_profile = None
    is_staff_user = request.user.is_staff or request.user.is_superuser
    
    if not is_staff_user:
        try:
            instructor_profile = request.user.instructor_profile
        except InstructorProfile.DoesNotExist:
            messages.error(request, 'Access Denied: Instructor privileges required.')
            return redirect('home')
    
    # Verify student is in instructor's section (skip for staff users)
    student = get_object_or_404(User, id=student_id)
    try:
        student_presence = student.studentpresence
    except StudentPresence.DoesNotExist:
        messages.error(request, 'Student not found in system.')
        return redirect('instructor_admin')
    
    if not is_staff_user and student_presence.section != instructor_profile.section:
        messages.error(request, 'You can only view students in your section.')
        return redirect('instructor_admin')
    
    # Get student profile
    try:
        profile = student.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=student)
    
    # Get student's activity records (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    sign_in_records = SignInRecord.objects.filter(
        student=student,
        sign_in_time__gte=thirty_days_ago
    ).order_by('-sign_in_time')[:15]
    
    # Get FRC attendance (current month)
    today = date.today()
    current_month_start = today.replace(day=1)
    frc_records = FlagRaisingCeremony.objects.filter(
        student=student,
        attendance_date__gte=current_month_start
    ).order_by('-attendance_date')
    
    frc_present = frc_records.filter(present=True).count()
    frc_total = frc_records.count()
    frc_percentage = round((frc_present / frc_total * 100) if frc_total > 0 else 0)
    
    # Get activity hours (current month)
    activity_hours = ActivityHour.objects.filter(
        student=student,
        sign_in_time__date__gte=current_month_start
    ).order_by('-sign_in_time')
    
    # Calculate statistics
    total_lab_hours = 0
    for record in sign_in_records:
        if record.duration_minutes():
            total_lab_hours += record.duration_minutes()
    
    total_lab_hours = round(total_lab_hours / 60, 1) if total_lab_hours else 0
    
    context = {
        'instructor_profile': instructor_profile,
        'student': student,
        'student_presence': student_presence,
        'profile': profile,
        'sign_in_records': sign_in_records,
        'frc_records': frc_records,
        'frc_present': frc_present,
        'frc_total': frc_total,
        'frc_percentage': frc_percentage,
        'activity_hours': activity_hours,
        'total_lab_hours': total_lab_hours,
    }
    
    return render(request, 'instructor_admin_student_detail.html', context)


# ============ ADMIN INSTRUCTOR MANAGEMENT ============

def admin_required(function):
    """Decorator to ensure only staff/superusers can access."""
    def wrap(request, *args, **kwargs):
        if not (request.user.is_staff or request.user.is_superuser):
            messages.error(request, 'Access Denied: Administrator privileges required.')
            return redirect('home')
        return function(request, *args, **kwargs)
    return wrap


@login_required(login_url='login')
@admin_required
def admin_system_dashboard(request):
    """
    ADMIN-ONLY System Dashboard for superusers/staff.
    Displays system administration controls and statistics.
    """
    # Get system statistics
    total_users = User.objects.count()
    
    # Count instructors: users with InstructorProfile
    total_instructors = InstructorProfile.objects.count()
    
    # Count students: users who are NOT staff/admin AND have no InstructorProfile
    # This correctly separates students from instructors and admin accounts
    total_students = User.objects.filter(
        is_staff=False,
        instructor_profile__isnull=True
    ).count()
    
    total_rooms = Room.objects.count()
    
    # Get all instructor accounts for management
    instructors = InstructorProfile.objects.select_related('user', 'section').order_by('-user__date_joined')
    
    context = {
        'total_users': total_users,
        'total_instructors': total_instructors,
        'total_students': total_students,
        'total_rooms': total_rooms,
        'instructors': instructors,
        'is_admin_dashboard': True,
    }
    
    return render(request, 'admin_system_dashboard.html', context)


@login_required(login_url='login')
@admin_required
def admin_user_management(request):
    """
    ADMIN-ONLY User Management for superusers/staff.
    Manage all users - delete accounts, profiles, and data.
    """
    # Handle photo upload
    if request.method == 'POST' and 'upload_photo_user_id' in request.POST:
        user_id = request.POST.get('upload_photo_user_id', '').strip()
        
        try:
            user_id_int = int(user_id)
            user = User.objects.get(id=user_id_int)
            
            if 'profile_picture' not in request.FILES:
                messages.error(request, 'No image file selected.')
            else:
                profile = user.profile
                # Delete old photo if exists
                if profile.profile_picture:
                    profile.profile_picture.delete()
                # Upload new photo
                profile.profile_picture = request.FILES['profile_picture']
                profile.save()
                messages.success(request, f'✓ Profile picture updated for "{user.username}".')
        except (ValueError, User.DoesNotExist):
            messages.error(request, 'User not found or invalid file.')
        except UserProfile.DoesNotExist:
            messages.error(request, 'User profile does not exist.')
        except Exception as e:
            messages.error(request, f'Error uploading image: {str(e)}')
        
        return redirect('admin_user_management')
    
    # Handle photo deletion (separate from clear data)
    if request.method == 'POST' and 'delete_photo_user_id' in request.POST:
        user_id = request.POST.get('delete_photo_user_id', '').strip()
        
        try:
            user_id_int = int(user_id)
            user = User.objects.get(id=user_id_int)
            
            profile = user.profile
            if profile.profile_picture:
                profile.profile_picture.delete()
                profile.save()
                messages.success(request, f'✓ Profile picture deleted for "{user.username}".')
            else:
                messages.info(request, f'No profile picture to delete for "{user.username}".')
        except (ValueError, User.DoesNotExist):
            messages.error(request, 'User not found.')
        except UserProfile.DoesNotExist:
            messages.error(request, 'User profile does not exist.')
        
        return redirect('admin_user_management')
    
    # Handle user deletion
    if request.method == 'POST' and 'delete_user_id' in request.POST:
        user_id = request.POST.get('delete_user_id', '').strip()
        
        try:
            user_id_int = int(user_id)
            user = User.objects.get(id=user_id_int)
            
            # Prevent deleting own account
            if user.id == request.user.id:
                messages.error(request, 'You cannot delete your own account.')
                return redirect('admin_user_management')
            
            username = user.username
            user_type = 'Staff/Admin' if user.is_staff else 'User'
            user.delete()
            messages.success(request, f'✓ {user_type} account "{username}" deleted successfully.')
        except (ValueError, User.DoesNotExist):
            messages.error(request, 'User not found or invalid ID.')
        
        return redirect('admin_user_management')
    
    # Handle profile data deletion
    if request.method == 'POST' and 'clear_user_data_id' in request.POST:
        user_id = request.POST.get('clear_user_data_id', '').strip()
        
        try:
            user_id_int = int(user_id)
            user = User.objects.get(id=user_id_int)
            
            # Clear profile data
            try:
                profile = user.profile
                if profile.profile_picture:
                    profile.profile_picture.delete()
                profile.bio = ''
                profile.phone_number = ''
                profile.save()
                messages.success(request, f'✓ Profile data cleared for "{user.username}".')
            except UserProfile.DoesNotExist:
                pass
        except (ValueError, User.DoesNotExist):
            messages.error(request, 'User not found.')
        
        return redirect('admin_user_management')
    
    # Get all users (excluding current user for display)
    # GET: Display users separated by account type
    all_users = User.objects.exclude(id=request.user.id).select_related('profile').order_by('-date_joined')
    
    # Separate by account type - NOT just by is_staff
    admin_users = all_users.filter(is_staff=True)  # Admin/superuser accounts
    instructor_users = all_users.filter(instructor_profile__isnull=False).distinct()  # Users with InstructorProfile
    student_users = all_users.filter(
        is_staff=False,
        instructor_profile__isnull=True
    )  # Regular students (no instructor role, not admin)
    
    # Calculate correct totals including current user for stats display
    total_admin_count = User.objects.filter(is_staff=True).count()
    total_instructor_count = User.objects.filter(instructor_profile__isnull=False).distinct().count()
    total_student_count = User.objects.filter(is_staff=False, instructor_profile__isnull=True).count()
    total_users_count = User.objects.count()
    
    context = {
        'admin_users': admin_users,
        'instructor_users': instructor_users,
        'student_users': student_users,
        'total_users': total_users_count,
        'total_admin_count': total_admin_count,
        'total_instructor_count': total_instructor_count,
        'total_student_count': total_student_count,
    }
    
    return render(request, 'admin_user_management.html', context)


@login_required(login_url='login')
@admin_required
def admin_instructor_management(request):
    """
    ADMIN-ONLY interface for creating and managing instructor accounts.
    
    SECURITY: Only staff/superusers can access. This prevents students from
    creating unauthorized instructor accounts.
    """
    # Get all instructors
    instructors = InstructorProfile.objects.select_related('user', 'section', 'instructor_room').order_by('user__first_name', 'user__last_name')
    
    # Get all available sections
    sections = Section.objects.all().order_by('year', 'section')
    rooms = Room.objects.all().order_by('name')
    
    # Handle instructor creation form submission
    if request.method == 'POST' and 'create_instructor' in request.POST:
        username = request.POST.get('username', '').strip().lower()
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        password = request.POST.get('password', '')
        section_id = request.POST.get('section')
        
        # Validation
        if not all([username, email, password, first_name, last_name]):
            messages.error(request, 'All fields are required.')
        elif len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
        elif User.objects.filter(username__iexact=username).exists():
            messages.error(request, f'Username "{username}" already exists.')
        elif User.objects.filter(email=email).exists():
            messages.error(request, f'Email "{email}" is already registered.')
        else:
            # Create user account
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_staff=False  # Instructor is not staff (different role system)
            )
            
            # Get section
            section = None
            if section_id:
                try:
                    section = Section.objects.get(id=section_id)
                except Section.DoesNotExist:
                    section = None
            
            # Create instructor profile
            InstructorProfile.objects.create(
                user=user,
                section=section,
                instructor_room=None
            )
            
            messages.success(request, f'✓ Instructor account "{username}" created successfully!')
            return redirect('admin_instructor_management')
    
    # Handle instructor editing
    if request.method == 'POST' and 'edit_instructor' in request.POST:
        instructor_id = request.POST.get('edit_instructor')
        section_id = request.POST.get('section')
        room_id = request.POST.get('room')
        
        try:
            instructor_profile = InstructorProfile.objects.get(user_id=instructor_id)
            
            # Update section
            if section_id:
                try:
                    instructor_profile.section = Section.objects.get(id=section_id)
                except Section.DoesNotExist:
                    instructor_profile.section = None
            else:
                instructor_profile.section = None
            
            # Update room
            if room_id:
                try:
                    instructor_profile.instructor_room = Room.objects.get(id=room_id)
                except Room.DoesNotExist:
                    instructor_profile.instructor_room = None
            else:
                instructor_profile.instructor_room = None
            
            instructor_profile.save()
            messages.success(request, f'✓ Instructor profile updated successfully!')
        except InstructorProfile.DoesNotExist:
            messages.error(request, 'Instructor not found.')
        
        return redirect('admin_instructor_management')
    
    # Handle instructor deletion
    if request.method == 'POST' and 'delete_instructor' in request.POST:
        instructor_id = request.POST.get('delete_instructor', '').strip()
        
        # Validate that instructor_id is not empty and is a valid integer
        if not instructor_id:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'Invalid instructor ID.'}, status=400)
            messages.error(request, 'Invalid instructor ID. Please try again.')
            return redirect('admin_instructor_management')
        
        try:
            instructor_id_int = int(instructor_id)
            user = User.objects.get(id=instructor_id_int)
            username = user.username
            user.delete()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': f'✓ Instructor account "{username}" deleted successfully!'})
            
            messages.success(request, f'✓ Instructor account "{username}" deleted successfully!')
        except ValueError:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'Invalid instructor ID format.'}, status=400)
            messages.error(request, 'Invalid instructor ID format.')
        except User.DoesNotExist:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'Instructor not found.'}, status=404)
            messages.error(request, 'Instructor not found.')
        
        return redirect('admin_instructor_management')
    
    context = {
        'instructors': instructors,
        'sections': sections,
        'rooms': rooms,
    }
    
    return render(request, 'admin_instructor_management.html', context)
