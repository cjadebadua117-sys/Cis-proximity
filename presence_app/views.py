# pyright: reportAttributeAccessIssue=false, reportOptionalMemberAccess=false, reportGeneralTypeIssues=false, reportMissingModuleSource=false
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
from django.views.decorators.http import require_http_methods
from .models import Room, StudentPresence, Section, UserProfile, InstructorProfile, SignInRecord, FlagRaisingCeremony, ActivityHour, PresenceSession, LaboratoryHistory, LegacyLaboratoryHistory, Broadcast
from .utils import is_on_university_wifi, get_client_ip
from django import forms
from django.db.models import Q, Sum, Exists, OuterRef
from django.utils import timezone
from datetime import datetime, timedelta, date
from pytz import timezone as tz
import calendar
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


class UnifiedRegistrationForm(UserCreationForm):
    """Unified registration form that can register both students and instructors."""
    email = forms.EmailField(required=True)
    user_type = forms.ChoiceField(
        choices=[('student', 'Student'), ('instructor', 'Instructor')],
        widget=forms.RadioSelect,
        label="Account Type"
    )
    student_id_number = forms.CharField(
        max_length=12,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'e.g., 241-0273-1'}),
        help_text='Format: XXX-XXXX-X (8 digits total)'
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'user_type', 'password1', 'password2')

    def clean_username(self):
        # normalize username to lowercase and strip whitespace; avoid
        # duplicates regardless of case.  returning lowercase ensures we
        # authenticate using the same form during login.
        username = self.cleaned_data.get('username', '').strip().lower()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('A user with that username already exists.')
        return username


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
    """Handle user registration via a single unified form."""
    # Clear any flash messages that may have been set by other views (e.g. the
    # logout view).  Without this, the "logged out successfully" message would
    # still show up on the registration page after clicking the "Register" link
    # on the login screen.
    for _ in messages.get_messages(request):
        pass

    if request.user.is_authenticated:
        return redirect('home')

    user_type = request.POST.get('user_type') or request.GET.get('type') or 'student'

    if request.method == 'POST':
        post_data = request.POST.copy()
        # Support single-password registration UX by mirroring password1 to password2.
        if post_data.get('password1') and not post_data.get('password2'):
            post_data['password2'] = post_data.get('password1')

        if 'user_type' not in post_data:
            post_data['user_type'] = 'instructor' if user_type == 'instructor' else 'student'

        form = UnifiedRegistrationForm(post_data)
        if form.is_valid():
            user = form.save()
            user_type_value = form.cleaned_data.get('user_type')

            if user_type_value == 'instructor':
                InstructorProfile.objects.create(user=user, section=None)
                messages.success(request, 'Instructor account created successfully! Please log in.')
            else:
                student_id_number = form.cleaned_data.get('student_id_number', '').strip()
                if student_id_number:
                    user.profile.student_id_number = student_id_number
                    user.profile.save()
                messages.success(request, 'Student account created successfully! Please log in.')

            return redirect('login')

        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f'{field}: {error}')
    else:
        form = UnifiedRegistrationForm(initial={'user_type': 'instructor' if user_type == 'instructor' else 'student'})

    return render(request, 'register.html', {
        'form': form,
        'user_type': user_type,
        'is_instructor': user_type == 'instructor',
        'use_unified_form': True,
    })

def login_view(request):
    """Handle user login."""
    # clear any leftover flash messages so the login page is always clean
    for _ in messages.get_messages(request):
        pass

    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        # normalize the username to lowercase to match registration behavior
        username = request.POST.get('username','').lower()
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            # authentication failed – do not flash any message to keep login page clean
            pass
    
    return render(request, 'login.html')


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
        is_instr = False

    context = {
        'form': form,
        'is_enrolled': current_presence and current_presence.section,
        'is_instructor': is_instr,
    }
    
    return render(request, 'enroll.html', context)


@login_required(login_url='login')
def dashboard(request):
    """Render the sign-in dashboard."""
    # Check if user is enrolled (students) or is an instructor with a section
    try:
        current_presence = StudentPresence.objects.get(student=request.user)
    except StudentPresence.DoesNotExist:
        current_presence = None

    # Allow instructors (class advisors) who have an assigned section to access without enrolling
    is_instructor_with_section = False
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
            messages.error(request, '❌ You must be connected to University Wi-Fi to enter a room.')
            return redirect('dashboard')
    
    # Get room_id from POST data if not in URL
    if room_id is None:
        room_id = request.POST.get('room_id')
    
    if not room_id:
        messages.error(request, 'Please select a room.')
        return redirect('dashboard')
    
    try:
        room = get_object_or_404(Room, id=room_id)
    except:
        messages.error(request, 'Room not found.')
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
            messages.info(request, f'You are already signed in to {room.name}.')
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
        messages.success(request, f'✓ Signed in to {room.name}')
    else:
        messages.success(request, f'✓ Updated location to {room.name}')
    
    return redirect('dashboard')


@login_required(login_url='login')
@require_http_methods(["POST"])
def sign_out(request):
    """Handle sign-out (mark as offline)."""
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

        messages.success(request, '✓ You have been signed out.')
    except StudentPresence.DoesNotExist:
        messages.error(request, 'No active sign-in found.')

    return redirect('dashboard')


@login_required(login_url='login')
def peer_search(request):
    """Search for peers and display their locations.
    
    When a search query is provided, show all classmates (enrolled students in the
    same section) who match the query, whether online or offline. Otherwise, show
    only classmates who are currently online.  Privacy settings are always respected.
    """
    query = request.GET.get('q', '').strip()
    results = None
    online_students = None
    
    # Get current user's section (if enrolled)
    try:
        current_section = request.user.studentpresence.section
    except (StudentPresence.DoesNotExist, AttributeError):
        current_section = None

    # Base queryset with profile preloaded for layout data (photo, student id, phone).
    base_qs = StudentPresence.objects.select_related('student', 'current_room', 'student__profile')

    # Privacy-aware filtering:
    # - ONLY_ME: never visible to others
    # - PUBLIC: visible to everyone
    # - FRIENDS_ONLY: visible only if the searching user has been added to their friends list
    visibility_q = Q(student=request.user) | Q(student__profile__privacy_level=UserProfile.PRIVACY_PUBLIC)
    
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
    online_students = base_qs.filter(
        Q(student__presence_sessions__is_active=True)
        | Q(student__sign_in_records__sign_out_time__isnull=True)
    ).exclude(student=request.user).order_by('-last_seen').distinct()

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
        # base_qs already respects privacy rules.
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
        # No query: keep results empty and show online list above.
        public_results = []
        custom_results = []
        results = None

    if results is not None:
        for row in results:
            _reconcile_status(row)
    if online_students is not None:
        for row in online_students:
            _reconcile_status(row)
    
    context = {
        'query': query,
        'public_results': public_results,
        'custom_results': custom_results,
        'online_students': online_students,
    }
    
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
    
    try:
        profile = user.profile  # type: ignore
    except UserProfile.DoesNotExist:
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
        is_instructor = False

    # If user has a presence record, check for an active SignInRecord. If there's no active sign-in,
    # clear the displayed current_room so templates can treat the user as "outside department".
    if presence:
        active_signin = SignInRecord.objects.filter(student=user, sign_out_time__isnull=True).exists()
        if not active_signin:
            presence.current_room = None
    
    if request.method == 'POST' and is_own_profile:
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            # Update user fields
            user.first_name = form.cleaned_data.get('first_name', '')
            user.last_name = form.cleaned_data.get('last_name', '')
            user.email = form.cleaned_data.get('email', '')
            user.save()
            
            # Update profile
            form.save()
            messages.success(request, '✓ Profile updated successfully!')
            return redirect(request.path)
    else:
        initial_data = {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
        }
        form = ProfileForm(instance=profile, initial=initial_data) if is_own_profile else None
    
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
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    upload = request.FILES.get('profile_picture')
    if not upload:
        return JsonResponse({'status': 'error', 'message': 'No file uploaded.'}, status=400)

    if upload.size > (5 * 1024 * 1024):
        return JsonResponse({'status': 'error', 'message': 'Image must be 5MB or less.'}, status=400)

    content_type = (upload.content_type or '').lower()
    if not content_type.startswith('image/'):
        return JsonResponse({'status': 'error', 'message': 'Invalid file type. Upload an image.'}, status=400)

    profile.profile_picture = upload
    profile.save()
    return JsonResponse({'status': 'ok', 'image_url': profile.profile_picture.url})


@login_required(login_url='login')
@require_http_methods(["POST"])
def privacy_update(request):
    """AJAX endpoint to update the logged-in user's privacy level and selected peers."""
    try:
        profile, created = UserProfile.objects.get_or_create(user=request.user)
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'Profile not found'}, status=400)

    new_level = request.POST.get('privacy_level')
    valid_levels = {c[0] for c in UserProfile.PRIVACY_CHOICES}
    if new_level not in valid_levels:
        return JsonResponse({'status': 'error', 'message': 'Invalid privacy level'}, status=400)

    profile.privacy_level = new_level
    
    # Handle selected peers for FRIENDS_ONLY privacy
    if new_level == UserProfile.PRIVACY_FRIENDS_ONLY:
        import json
        selected_peers_json = request.POST.get('selected_peers', '[]')
        try:
            selected_peer_ids = json.loads(selected_peers_json)
            # Clear existing friends and add selected ones
            profile.friends.clear()
            for peer_id in selected_peer_ids:
                try:
                    peer_user = User.objects.get(id=peer_id)
                    profile.friends.add(peer_user)
                except User.DoesNotExist:
                    pass
        except json.JSONDecodeError:
            pass
    
    profile.save()

    return JsonResponse({'status': 'ok', 'privacy_level': profile.privacy_level})


@login_required(login_url='login')
def search_peers_api(request):
    """
    API endpoint to search for peers by username.  Used both by the peer
    discovery page and by the privacy manager when adding allowed friends.
    
    Privacy rules are evaluated from the perspective of the account being
    queried (i.e. the user whose name is being searched):

    - PUBLIC: everyone can see the user.
    - FRIENDS_ONLY ("Custom"): only people explicitly added to that user's
      friends/access list may see them.
    - ONLY_ME: the user never appears in search results for anyone else.

    When invoked from the privacy manager the returned list is also filtered
    to remove any users that the searching account has already added (so you
    cannot add the same friend twice).
    """
    query = request.GET.get('q', '').strip()
    
    if len(query) < 1:
        return JsonResponse({'peers': [], 'results': []})
    
    # Get the searching user's section for classmate verification
    try:
        searcher_presence = StudentPresence.objects.get(student=request.user)
        searcher_section = searcher_presence.section
    except StudentPresence.DoesNotExist:
        # If searcher has no section, they can only see PUBLIC users
        searcher_section = None
    
    # Build the query to find matching users
    matching_users = User.objects.filter(
        Q(username__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query),
        studentpresence__isnull=False  # Only actual students
    ).exclude(id=request.user.id).distinct()
    
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
        try:
            user_profile = user.profile
            user_presence = user.studentpresence
            
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
        
        except (UserProfile.DoesNotExist, StudentPresence.DoesNotExist):
            # Skip users without profiles
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
        return JsonResponse({'status': 'ok', 'allowed_friends': friends_list})
    except UserProfile.DoesNotExist:
        return JsonResponse({'status': 'ok', 'allowed_friends': []})


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
            return JsonResponse({'status': 'error', 'message': 'Friend ID required'}, status=400)
        
        try:
            friend_user = User.objects.get(id=friend_id)
            profile.friends.add(friend_user)
            profile.save()
            return JsonResponse({'status': 'ok', 'message': f'Added {friend_user.username} to access list'})
        except User.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'User not found'}, status=404)
    except UserProfile.DoesNotExist:
        # Create profile if doesn't exist
        profile = UserProfile.objects.create(user=request.user)
        friend_id = json.loads(request.body).get('friend_id')
        try:
            friend_user = User.objects.get(id=friend_id)
            profile.friends.add(friend_user)
            return JsonResponse({'status': 'ok', 'message': f'Added {friend_user.username} to access list'})
        except User.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


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
            return JsonResponse({'status': 'error', 'message': 'Friend ID required'}, status=400)
        
        try:
            friend_user = User.objects.get(id=friend_id)
            profile.friends.remove(friend_user)
            profile.save()
            return JsonResponse({'status': 'ok', 'message': f'Removed {friend_user.username} from access list'})
        except User.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'User not found'}, status=404)
    except UserProfile.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Profile not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


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
    # Check if user is an instructor
    try:
        instructor_profile = request.user.instructor_profile
    except InstructorProfile.DoesNotExist:
        messages.error(request, 'You do not have instructor privileges.')
        return redirect('home')
    
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
    # Check if user is an instructor
    try:
        instructor_profile = request.user.instructor_profile
    except InstructorProfile.DoesNotExist:
        messages.error(request, 'You do not have instructor privileges.')
        return redirect('home')
    
    section = instructor_profile.section
    today = timezone.now().astimezone(tz('Asia/Manila')).date()
    recent_cutoff = today - timedelta(days=7)

    if not section:
        activities = ActivityHour.objects.none()
        recent_activities = ActivityHour.objects.none()
        messages.warning(request, 'No section assigned yet. Ask an administrator to assign your section.')
    else:
        # Primary panel: today's sessions
        activities = ActivityHour.objects.filter(
            student__studentpresence__section=section,
            sign_in_time__date=today
        ).select_related('student').order_by('-sign_in_time')

        # Secondary panel: last 7 days (including today) so instructors can still adjust records
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
    if not is_on_university_wifi(request):
        messages.error(request, '⚠ You must be connected to campus Wi-Fi to sign in.')
        return redirect('home')
    
    if request.method == 'POST':
        room_id = request.POST.get('room')
        
        if not room_id:
            messages.error(request, 'Please select a room.')
            return redirect('presence_signin')
        
        try:
            room = Room.objects.get(id=room_id)
        except Room.DoesNotExist:
            messages.error(request, 'Invalid room selected.')
            return redirect('presence_signin')
        
        # Get client IP
        client_ip = get_client_ip(request)
        
        # Check if user already has an active session
        active_session = PresenceSession.objects.filter(
            user=request.user,
            is_active=True
        ).first()
        
        if active_session:
            messages.warning(request, f'You already have an active session in {active_session.room.name}. Please sign out first.')
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
        
        messages.success(request, f'✓ Signed in to {room.name}. Your location is now visible to peers.')
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
    # Find active session
    active_session = PresenceSession.objects.filter(
        user=request.user,
        is_active=True
    ).first()
    
    if not active_session:
        messages.warning(request, 'You do not have an active session.')
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
        
        messages.success(request, f'✓ Signed out from {room_name}. Session duration: {duration} minutes.')
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
            
            users = User.objects.filter(
                Q(username__icontains=query) |
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query)
            ).exclude(id=request.user.id)  # Exclude self
            
            # Get active sessions for these users while respecting privacy
            for user in users:
                try:
                    user_profile = user.profile
                    user_presence = user.studentpresence
                    
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
                            })
                        continue
                    
                    # RULE 3: CUSTOM (FRIENDS_ONLY) - Show only to people on their access list
                    if user_profile.privacy_level == UserProfile.PRIVACY_FRIENDS_ONLY:
                        # only allow if searching user is in their friends list
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
                                })
                        # otherwise do not include them
                        continue
                
                except (UserProfile.DoesNotExist, StudentPresence.DoesNotExist):
                    # Skip users without profiles
                    continue
            
            if not results and len(query) >= 2:
                error = f"No active peers found matching '{query}'."
    
    context = {
        'query': query,
        'results': results,
        'error': error,
    }
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
    
    context = {
        'active_session': active_session,
        'session_history': session_history,
        'frc_total': frc_total,
        'frc_absent': frc_absent,
        'activity_hours': activity_hours_sessions,
        'is_on_campus': is_on_university_wifi(request),
    }
    return render(request, 'presence_dashboard.html', context)


@login_required
def laboratory_history(request):
    """
    Display Laboratory History - instructor-only view for automatic exit tracking.
    Shows when students exited labs and how long they spent there.
    """
    # Restrict access to instructors only
    try:
        is_instructor = hasattr(request.user, 'instructor_profile') or request.user.is_staff
    except Exception:
        is_instructor = False

    if not request.user.is_authenticated or not is_instructor:
        from django.contrib import messages
        messages.error(request, 'Access denied — laboratory history is for instructors only.')
        return redirect('dashboard')

    # Keep profile fetch for template/context safety
    try:
        instructor_profile = request.user.instructor_profile
    except InstructorProfile.DoesNotExist:
        instructor_profile = None

    # Build rows from SignInRecord directly so displayed entrance/exit times
    # are exact (no inferred timestamps).
    lab_rows = []
    total = 0
    
    try:
        lab_room_filter = Q(room__name__icontains='lab') | Q(room__name__icontains='orc')
        qs = (SignInRecord.objects.select_related('student', 'room')
              .filter(lab_room_filter)
              .order_by('-sign_in_time'))
        
        total = qs.count()
        
        for r in qs:
            # Resolve student's section for instructor clarity
            section_name = ''
            try:
                sp = r.student.studentpresence
                if sp and sp.section:
                    section_name = str(sp.section)
            except Exception:
                section_name = ''

            # Get student ID number from profile
            student_id_number = ''
            try:
                profile = r.student.profile
                if profile and profile.student_id_number:
                    student_id_number = profile.student_id_number
            except Exception:
                student_id_number = ''

            if r.sign_out_time:
                duration_minutes = r.duration_minutes()
            else:
                # Active lab session: compute running duration.
                duration_minutes = int((timezone.now() - r.sign_in_time).total_seconds() / 60)

            duration_hours = int(duration_minutes // 60) if duration_minutes else 0
            duration_minutes_remainder = int(duration_minutes % 60) if duration_minutes else 0

            # append record
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
        # if history fetch fails just continue with empty list
        pass

    # allow CSV export
    if request.GET.get('export') == 'csv':
        import csv
        from django.http import HttpResponse
        resp = HttpResponse(content_type='text/csv')
        resp['Content-Disposition'] = 'attachment; filename="lab_history.csv"'
        writer = csv.writer(resp)
        # provide a richer export with username, full name, section, and ID
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

    # Group rows by the date of entry (entrance_time) where available,
    # otherwise fall back to exit_time. Use Philippines timezone for date grouping.
    from collections import defaultdict
    philippines_tz = tz('Asia/Manila')
    groups = defaultdict(list)

    for r in lab_rows:
        dt = r.get('entrance_time') or r.get('exit_time')
        if not dt:
            # Skip records without any timestamp
            continue
        try:
            # Ensure timezone-aware conversion where possible
            date_key = dt.astimezone(philippines_tz).date() if hasattr(dt, 'astimezone') else dt.date()
        except Exception:
            date_key = dt.date()
        groups[date_key].append(r)

    # Build ordered list of days (most recent first)
    grouped_days = []
    for day in sorted(groups.keys(), reverse=True):
        # Sort each day's records with most recent exit_time first
        records = sorted(groups[day], key=lambda x: x.get('exit_time') or x.get('entrance_time'), reverse=True)
        grouped_days.append({
            'date': day,
            'display': day.strftime('%B %d, %Y'),
            'records': records,
            'count': len(records),
        })

    # Build sparkline data for the past 7 days (including today)
    from django.utils import timezone
    from datetime import timedelta
    today = timezone.now().date()
    sparkline = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        sparkline.append(len(groups.get(d, [])))

    # convert to SVG point string (scale x by 10, invert y for 24px height)
    points = []
    for idx, v in enumerate(sparkline):
        x = idx * 10
        y = 24 - v
        points.append(f"{x},{y}")
    sparkline_points = ' '.join(points)

    context = {
        'grouped_days': grouped_days,
        'total_exits': total,
        'sparkline_data': sparkline,  # list of 7 integers oldest->newest
        'sparkline_points': sparkline_points,
    }
    return render(request, 'laboratory_history.html', context)
