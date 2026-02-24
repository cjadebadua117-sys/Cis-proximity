# CIS-Prox API Reference

## Overview
CIS-Prox endpoints for network-authenticated student presence and peer discovery.

---

## Authentication
All endpoints require user to be logged in. Anonymous users are redirected to login.

```
Decorator: @login_required(login_url='login')
```

---

## Endpoints

### 1. Sign In to Location
**URL**: `/presence/signin/`  
**Methods**: GET (form), POST (submit)  
**Auth**: Required  
**Network Check**: ✅ Yes (must be on campus Wi-Fi)

#### GET Request
Returns sign-in form with room selection.

**Response**: HTML form
```html
<select name="room">
  <option value="1">📍 Laboratory 1</option>
  <option value="2">📍 Laboratory 2</option>
  <option value="3">📍 Room 301</option>
</select>
```

**Template**: `presence_signin.html`

#### POST Request
Submit sign-in with selected room.

**Parameters**:
```
room: <int>  # Room ID (required)
```

**Success Response**:
- Creates PresenceSession in database
- Redirects to `/presence/dashboard/`
- Message: "✓ Signed in to {room}. Your location is now visible to peers."

**Error Responses**:
- ⚠ Not on campus Wi-Fi → Redirected to home with error
- No room selected → Back to form with error
- Invalid room ID → Back to form with error

**Database Effect**:
```python
PresenceSession.objects.create(
    user=request.user,
    room=room,
    ip_address=client_ip,
    is_verified=True,
    is_active=True
)
```

---

### 2. Sign Out
**URL**: `/presence/signout/`  
**Methods**: GET (confirmation), POST (submit)  
**Auth**: Required  
**Network Check**: None (can sign out anywhere)

#### GET Request
Shows confirmation dialog with current session details.

**Template**: `presence_signout.html`

**Context Data**:
```python
{
    'session': {
        'room': Room,
        'signed_in_at': datetime,
        'duration_minutes': int
    }
}
```

#### POST Request
Confirms and ends active session.

**Parameters**: None (CSRF token required)

**Success Response**:
- Updates PresenceSession: `signed_out_at = now()`, `is_active = False`
- Redirects to `/presence/dashboard/`
- Message: "✓ Signed out from {room}. Session duration: {minutes} minutes."

**Error Responses**:
- No active session → Redirected to dashboard with warning

**Database Effect**:
```python
session.mark_signed_out()  # Sets signed_out_at and is_active=False
```

---

### 3. Peer Search
**URL**: `/presence/search/`  
**Methods**: GET  
**Auth**: Required  
**Network Check**: None

#### GET Request
Search for active peers.

**Parameters**:
```
q: <string>  # Search query (min 2 chars, optional)
```

**Example Requests**:
```
/presence/search/
/presence/search/?q=Marco
/presence/search/?q=john
```

**Response**: HTML with results

**Template**: `presence_search.html`

**Context Data** (when q provided):
```python
{
    'query': 'Marco',
    'results': [
        {
            'user': User,
            'room': Room,
            'signed_in_at': datetime,
            'duration': int  # minutes
        },
        ...
    ],
    'error': None  # or error message
}
```

**Result Format** (HTML):
```
🔍 Found 1 active peer(s) matching "Marco"

📍 Marco (@marco_user)
Location: Laboratory 1
Duration: 25 minutes
Signed in: 14:30
```

**Search Behavior**:
- Searches User.username, User.first_name, User.last_name (case-insensitive)
- Excludes current user from results
- Only shows active, verified sessions
- Requires min 2 characters (else error: "Please enter at least 2 characters")
- No results message: "No active peers found matching '{query}'"

**Database Query**:
```python
users = User.objects.filter(
    Q(username__icontains=query) |
    Q(first_name__icontains=query) |
    Q(last_name__icontains=query)
).exclude(id=request.user.id)

for user in users:
    session = PresenceSession.objects.filter(
        user=user,
        is_active=True,
        is_verified=True
    ).first()
```

---

### 4. Presence Dashboard
**URL**: `/presence/dashboard/`  
**Methods**: GET  
**Auth**: Required  
**Network Check**: Status shown (but not blocking)

#### GET Request
Displays personal presence and attendance summary.

**Template**: `presence_dashboard.html`

**Context Data**:
```python
{
    'active_session': PresenceSession | None,
    'session_history': QuerySet[PresenceSession],  # Last 30 days, max 20
    'frc_total': int,
    'frc_absent': int,
    'activity_hours': QuerySet[ActivityHour],  # Max 10
    'is_on_campus': bool
}
```

**Response**: HTML Dashboard

**Sections**:

1. **Network & Active Session**
   - Current status (🟢 Active / 🔴 Offline)
   - Room, duration, sign-in time
   - Sign out button (if active)
   - Quick action links

2. **Attendance Summary**
   - FRC absences count
   - Activity hours sessions count
   - Quick stats cards

3. **Quick Actions**
   - Find Classmates (→ /presence/search/)
   - My Profile (→ /profile/{username}/)
   - Attendance (→ /attendance/)

4. **Recent Sessions** (last 30 days, max 20 shown)
   - Table: Location | Signed In | Duration | Status
   - Shows 🟢 Active or closed sessions
   - Timestamps in "M d H:i" format

5. **Recent Activity Hours** (last 10)
   - Table: Signed In | Signed Out | Duration | Status
   - Shows hours or 🟢 Active badge
   - Activity hour data

**SQL Queries Performed**:
```python
# Active session
PresenceSession.objects.filter(
    user=request.user,
    is_active=True
).first()

# Session history (30 days, limit 20)
PresenceSession.objects.filter(
    user=request.user,
    signed_in_at__gte=timezone.now() - timedelta(days=30)
).order_by('-signed_in_at')[:20]

# FRC stats
FlagRaisingCeremony.objects.filter(student=request.user).count()
FlagRaisingCeremony.objects.filter(
    student=request.user,
    present=False
).count()

# Activity hours
ActivityHour.objects.filter(student=request.user).order_by('-sign_in_time')[:10]
```

---

## URL Patterns

```python
# In swrs_config/urls.py
path('presence/signin/', views.presence_signin, name='presence_signin'),
path('presence/signout/', views.presence_signout, name='presence_signout'),
path('presence/search/', views.presence_search, name='presence_search'),
path('presence/dashboard/', views.presence_dashboard, name='presence_dashboard'),
```

**Template Tags**:
```django
{% url 'presence_signin' %}      → /presence/signin/
{% url 'presence_signout' %}     → /presence/signout/
{% url 'presence_search' %}      → /presence/search/
{% url 'presence_dashboard' %}   → /presence/dashboard/
```

---

## Error Handling

### Common Error Messages

| Condition | Message | Action |
|-----------|---------|--------|
| Not on campus Wi-Fi | "⚠ You must be connected to campus Wi-Fi to sign in." | Redirect to home |
| Already signed in | "You already have an active session in {room}. Please sign out first." | Stay on signin page |
| No room selected | "Please select a room." | Reload form |
| Invalid room | "Invalid room selected." | Reload form |
| No active session | "You do not have an active session." | Redirect to dashboard |
| Search < 2 chars | "Please enter at least 2 characters." | Show on search page |
| No search results | "No active peers found matching '{query}'." | Show on search page |

---

## HTTP Status Codes

| Code | Scenario |
|------|----------|
| 200 | GET request successful (form displayed) |
| 302 | POST successful (redirect) |
| 403 | User not authenticated (redirected to login) |
| 404 | Invalid room ID in POST |

---

## Data Models Used

### PresenceSession
```python
class PresenceSession(models.Model):
    user: ForeignKey(User)
    room: ForeignKey(Room, null=True)
    ip_address: GenericIPAddressField
    is_verified: BooleanField
    signed_in_at: DateTimeField(auto_now_add=True)
    signed_out_at: DateTimeField(null=True)
    is_active: BooleanField
    
    def duration_minutes(): int
    def mark_signed_out(): None
```

---

## Security Features

### 1. Network Verification
```python
is_on_university_wifi(request)
# Checks: IP in CAMPUS_WIFI_SUBNETS
# Returns: True/False
# Dev mode: Always True
```

### 2. CSRF Protection
All POST requests require CSRF token:
```django
{% csrf_token %}
```

### 3. IP Logging
Every session records client IP:
```python
ip_address = get_client_ip(request)
```

### 4. Authentication Required
```python
@login_required(login_url='login')
```

---

## Rate Limiting (Future Enhancement)

Recommended limits for production:
- /presence/signin/: 10 requests/minute per user
- /presence/search/: 30 requests/minute per user
- /presence/signout/: 5 requests/minute per user

---

## Example Workflows

### Workflow 1: Complete Sign-In → Search → Sign-Out

```bash
# 1. GET sign-in form
GET /presence/signin/
← Returns form with room dropdown

# 2. POST sign-in
POST /presence/signin/
  Data: room=1
← Creates PresenceSession
← Redirect to /presence/dashboard/

# 3. Search for peers
GET /presence/search/?q=marco
← Returns search results if Marco is signed in

# 4. Sign out
POST /presence/signout/
← Updates PresenceSession (sets signed_out_at, is_active=False)
← Redirect to /presence/dashboard/
```

### Workflow 2: Dashboard View

```bash
# User navigates to dashboard
GET /presence/dashboard/

Response includes:
- Active session (if any)
- Last 20 sessions (30 days)
- FRC stats
- Activity hour logs
- Quick action buttons
```

---

## Admin Panel

**URL**: `/admin/presence_app/presencesession/`

**Features**:
- List all sessions (sortable, filterable, searchable)
- Filter by: is_active, is_verified, room, date
- Search by: username, email, IP address
- View: User, Room, Status, Sign-in time, Duration, IP
- Readonly fields: signed_in_at, ip_address

---

## Configuration

**Settings** (`swrs_config/settings.py`):
```python
# Campus Wi-Fi subnets (CIDR notation)
CAMPUS_WIFI_SUBNETS = [
    '192.168.0.0/16',
    '10.0.0.0/8',
]

# Debug mode (True = bypass IP check)
DEBUG = True  # Development
DEBUG = False  # Production
```

---

**Version**: 1.0  
**Last Updated**: February 2, 2026
