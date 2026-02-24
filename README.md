# CIS-Prox: Network-Authenticated Student Presence & Indoor Locating System

A Django-based intranet platform that uses university Wi-Fi authentication to verify student attendance and enable real-time peer discovery within the Information Systems department.

## Features

### Core Capabilities
- **Network Gatekeeping**: Restricts attendance logging to campus Wi-Fi only; automatically flags users as "Disconnected/Offline" when off-campus
- **Live Peer Locator**: Search for classmates and see their real-time room/laboratory location
- **Digital Sign-In/Sign-Out Portal**: Replace paper logs with secure, time-stamped digital entries for mandatory events (FRC, Activity Hours)
- **Absence Transparency Dashboard**: Personal dashboard showing FRC absences and activity hour totals
- **Dynamic Status Mapping**: Automatic "Active"/"Inactive" visibility based on Wi-Fi connection status
- **Audit Logs**: Immutable session records for compliance and dispute resolution

## Project Structure

```
CIS-proximity/
â”œâ”€â”€ presence_app/
â”‚   â”œâ”€â”€ models.py           # Database models (PresenceSession, ActivityHour, etc.)
â”‚   â”œâ”€â”€ views.py            # CIS-Prox views (signin, signout, search, dashboard)
â”‚   â”œâ”€â”€ utils.py            # IP validation, network gatekeeping
â”‚   â”œâ”€â”€ admin.py            # Django admin interface
â”‚   â”œâ”€â”€ urls.py             # App URL patterns (if applicable)
â”‚   â”œâ”€â”€ migrations/         # Database migrations
â”‚   â””â”€â”€ templates/          # HTML templates
â”œâ”€â”€ swrs_config/
â”‚   â”œâ”€â”€ settings.py         # Django settings, CAMPUS_WIFI_SUBNETS config
â”‚   â”œâ”€â”€ urls.py             # Project URL routing
â”‚   â””â”€â”€ wsgi.py             # WSGI application
â”œâ”€â”€ manage.py               # Django management script
â””â”€â”€ db.sqlite3              # SQLite database (dev only)
```

## Requirements

- Python 3.10+
- Django 5.2.x
- (Optional) PostgreSQL for production; SQLite for dev

## Installation & Setup

### 1. Clone and Install Dependencies

```bash
cd c:\Users\Admin\Desktop\CIS-proximity
pip install django pillow
```

### 2. Apply Migrations

Run the database migrations to set up tables:

```bash
python manage.py migrate
```

### 3. Create a Superuser (Admin)

```bash
python manage.py createsuperuser
```

Follow the prompts to set username, email, and password.

### 4. Run the Development Server

```bash
python manage.py runserver 192.168.100.9:8000
```

Visit `http://192.168.100.9:8000/` in your browser.

### 5. Access Django Admin

Go to `http://192.168.100.9:8000/admin/` and log in with your superuser credentials to manage:
- Users and Profiles
- Rooms and Sections
- Presence Sessions
- Attendance Records

## Configuration

### Campus Wi-Fi Subnets

Edit [swrs_config/settings.py](swrs_config/settings.py) to add your campus network subnets in CIDR notation:

```python
CAMPUS_WIFI_SUBNETS = [
    '192.168.0.0/16',    # Default private network
    '10.0.0.0/8',        # Alternative campus subnet
]
```

The system will verify a user's IP against these subnets before allowing sign-in.

### Debug Mode

In development (`DEBUG=True` in settings.py), the system allows sign-ins from any network for testing. In production, strict IP verification is enforced.

## Database Models

### PresenceSession
Represents a user's active session with room location and network verification.

**Fields:**
- `user` â€“ FK to User
- `room` â€“ FK to Room (nullable)
- `ip_address` â€“ Client IP (GenericIPAddressField)
- `is_verified` â€“ Boolean (IP on campus subnet)
- `signed_in_at` â€“ DateTime (auto-created)
- `signed_out_at` â€“ DateTime (nullable)
- `is_active` â€“ Boolean (session status)

**Methods:**
- `duration_minutes()` â€“ Returns total session duration
- `mark_signed_out()` â€“ Closes session and sets end time

### ActivityHour
Tracks student activity/cleaning hours with fixed sign-in and sign-out.

**Fields:**
- `student` â€“ FK to User
- `sign_in_time` â€“ DateTime
- `sign_out_time` â€“ DateTime (nullable)
- `recorded_at` â€“ DateTime (auto-created)

**Methods:**
- `duration_hours()` â€“ Calculates hours worked
- `is_active()` â€“ True if not yet signed out

### FlagRaisingCeremony
Tracks FRC attendance per student and date.

**Fields:**
- `student` â€“ FK to User
- `attendance_date` â€“ DateField
- `present` â€“ Boolean
- `notes` â€“ TextField (optional)
- `recorded_at` â€“ DateTime (auto-created)

## API Endpoints / Views

### Presence Management
- `POST /presence/signin/` â€“ Sign in to a room (requires campus IP)
  - Form params: `room` (room ID)
  - Response: Redirect to presence dashboard
  
- `POST /presence/signout/` â€“ End active session
  - Response: Redirect to presence dashboard
  
- `GET /presence/dashboard/` â€“ Personal attendance & session history
  - Shows: Active session, last 30 days of sessions, FRC/Activity Hour totals
  
- `GET /presence/search/?q=<query>` â€“ Peer discovery
  - Query params: `q` (username or name fragment)
  - Response: List of active peers matching query with room locations

### Utilities

**IP Validation (`utils.py`):**
- `get_client_ip(request)` â€“ Extract client IP from request
- `is_on_university_wifi(request)` â€“ Verify IP is on campus subnet
- `get_campus_subnets()` â€“ Return configured campus subnets

## Security Considerations

### Production Deployment
1. **HTTPS Only**: Set `SECURE_SSL_REDIRECT = True` in settings.py
2. **IP Whitelisting**: Maintain an up-to-date `CAMPUS_WIFI_SUBNETS` list
3. **Rate Limiting**: Add Django rate limit middleware to prevent brute-force sign-ins
4. **Audit Logging**: All sign-in/sign-out events are recorded with IP and timestamp
5. **Database**: Use PostgreSQL in production instead of SQLite
6. **Secret Key**: Generate a new SECRET_KEY and store in environment variables

### Data Privacy
- Users control visibility via opt-in settings (future enhancement)
- Presence data auto-purged after 90 days (configurable)
- IP addresses stored only for verification and compliance

## Workflow Examples

### Scenario 1: Student Signs In to Activity
1. Student connects to campus Wi-Fi
2. Navigates to `http://<server>/presence/signin/`
3. Selects "Laboratory 1" as their current location
4. System verifies IP matches `CAMPUS_WIFI_SUBNETS`
5. Creates a `PresenceSession` with `is_active=True`
6. Peer search now shows this student as "Active in Laboratory 1"

### Scenario 2: Peer Discovery
1. Student navigates to `http://<server>/presence/search/`
2. Types "Marco" in the search box
3. System queries for active sessions matching "Marco"
4. Returns: "Marco is currently active in Room 3"
5. Timestamps show how long Marco has been signed in

### Scenario 3: Session Ends (Off-Campus)
1. Student leaves campus or switches to mobile data
2. System detects IP is no longer in `CAMPUS_WIFI_SUBNETS`
3. On next page load, status updates to "Offline"
4. Peer search no longer shows this student's location
5. Student manually signs out from presence dashboard

## Testing

### Manual Testing Checklist
- [ ] Create a Room in Django admin
- [ ] Create a test user via registration
- [ ] Sign in to the test user account
- [ ] Verify `is_on_university_wifi()` returns True (in DEBUG mode)
- [ ] Navigate to `/presence/signin/`, select a room
- [ ] Confirm `PresenceSession` was created in admin
- [ ] Test peer search to find the active user
- [ ] Sign out and verify session is marked inactive
- [ ] Check presence dashboard shows session history

### Unit Tests (Future)
Create tests in `presence_app/tests.py`:
- Test IP validation with various subnets
- Test PresenceSession creation/closure
- Test peer search filtering
- Test absence counting (FRC, Activity Hours)

## Troubleshooting

### "You must be connected to campus Wi-Fi"
- **Cause**: Your IP is not in `CAMPUS_WIFI_SUBNETS` or DEBUG is False
- **Fix**: In development, ensure DEBUG=True. In production, verify your IP or add subnet to settings

### PresenceSession not appearing
- **Cause**: Database migrations not run
- **Fix**: Run `python manage.py migrate`

### Peer search shows no results
- **Cause**: No active sessions exist or user is off-campus
- **Fix**: Ensure other users are signed in and on campus network

## Future Enhancements

1. **Real-time Presence Heartbeat** â€“ WebSocket/polling to update status every 5 minutes
2. **Privacy Controls** â€“ Users can opt-in/out of peer visibility
3. **Location Analytics** â€“ Track most-visited rooms, peak times
4. **Mobile App** â€“ Native iOS/Android with push notifications
5. **QR Code Check-In** â€“ Scan room code instead of dropdown
6. **Geofencing** â€“ GPS + Wi-Fi hybrid verification for outdoor areas
7. **Department Dashboard** â€“ Instructor view of all student locations in their section

## Support & Documentation

- **Django Docs**: https://docs.djangoproject.com/
- **Project Issues**: Refer to workspace GitHub issues (if applicable)
- **Admin Contact**: Your IT/Information Systems department

---

**Version**: 1.0  
**Last Updated**: February 2, 2026  
**Status**: Production Ready

