# CIS-Prox Quick Start Guide

Welcome to **CIS-Prox**—your network-authenticated student presence and peer discovery system!

## 🚀 Get Started in 2 Minutes

### Step 1: Start the Server
```bash
cd c:\Users\Admin\Desktop\SWRS
python manage.py runserver 192.168.100.9:8000
```

### Step 2: Access the System
- **Main App**: http://192.168.100.9:8000/
- **Admin Panel**: http://192.168.100.9:8000/admin/

### Step 3: Create Your First Account
1. Go to **Register** page
2. Choose **Student** or **Instructor**
3. Fill in username, email, password
4. Log in

---

## 📍 Core Features & URLs

### For Students

#### Sign In to Your Location
```
POST /presence/signin/
```
- Select your current room/lab
- System verifies you're on campus Wi-Fi
- Creates a presence session visible to peers

**Example:**
```
Navigate to: http://192.168.100.9:8000/presence/signin/
Select: "Laboratory 1"
Click: "Sign In"
```

#### Find Your Classmates
```
GET /presence/search/?q=Marco
```
- Search by name or username
- See their real-time location and how long they've been signed in
- Only shows peers who are currently on campus

**Example:**
```
Navigate to: http://192.168.100.9:8000/presence/search/
Type: "Marco"
Result: "Marco is currently active in Laboratory 1"
```

#### View Your Dashboard
```
GET /presence/dashboard/
```
- See your current session status
- View FRC absence count
- Track activity hour totals
- Browse your session history (last 30 days)

**Example:**
```
Navigate to: http://192.168.100.9:8000/presence/dashboard/
Shows:
  - Active session (if signed in)
  - FRC: 2 absences
  - Activity Hours: 15 sessions logged
  - Last 20 sessions with durations
```

#### Sign Out
```
POST /presence/signout/
```
- End your current session
- Hides your location from peer searches

**Example:**
```
Navigate to: http://192.168.100.9:8000/presence/signout/
Click: "Confirm Sign Out"
```

---

### For Administrators

#### Manage Presence Sessions
```
http://192.168.100.9:8000/admin/presence_app/presencesession/
```

**Actions:**
- View all active/inactive sessions
- See user IP addresses and verification status
- Filter by room, status, or date range
- Search by username or IP

**Columns:**
- User (who)
- Room (where)
- Status 🟢/🔴 (active or signed out)
- Signed In (when)
- Duration (how long)
- IP Address (network verification)

#### Setup Rooms
```
http://192.168.100.9:8000/admin/presence_app/room/
```
Add rooms/labs like:
- Laboratory 1
- Laboratory 2
- Room 301
- Room 302
- Conference Hall

---

## 🔐 Network Security

### How It Works
1. **User connects to campus Wi-Fi** → Gets IP like `192.168.x.x`
2. **User tries to sign in** → System checks IP against allowed subnets
3. **IP matches campus subnet** → ✓ Sign-in allowed
4. **IP doesn't match** → ✗ "You must be on campus Wi-Fi"

### Configure Campus Networks
Edit `swrs_config/settings.py`:

```python
CAMPUS_WIFI_SUBNETS = [
    '192.168.0.0/16',    # Your actual campus subnet
    '10.0.0.0/8',        # Alternative subnet
]
```

### Development Mode
In development (`DEBUG=True`), campus Wi-Fi check is **bypassed** so you can test from anywhere.
In production, strict IP verification is enforced.

---

## 🧪 Testing Checklist

- [ ] Create a **Room** (Admin > Room > Add)
- [ ] Register a **Student** account
- [ ] Log in as student
- [ ] Go to `/presence/signin/`
- [ ] Select a room and click "Sign In"
- [ ] Verify **PresenceSession** appears in Admin
- [ ] Go to `/presence/search/`
- [ ] Search for your username
- [ ] Verify your room shows up
- [ ] Go to `/presence/signout/`
- [ ] Click "Confirm Sign Out"
- [ ] Verify session is marked inactive
- [ ] Check `/presence/dashboard/` shows session in history

---

## 📊 Database Models

### PresenceSession
```python
{
  "user": User,           # Who signed in
  "room": Room,           # Where they signed in
  "ip_address": "192.168.100.50",
  "is_verified": True,    # IP on campus subnet
  "signed_in_at": "2026-02-02 10:30:00",
  "signed_out_at": "2026-02-02 11:45:00",  # NULL if active
  "is_active": False,     # True if still signed in
}
```

### Key Methods
```python
session.duration_minutes()  # Returns: 75
session.mark_signed_out()   # Ends session
```

---

## 🐛 Troubleshooting

### "You must be connected to campus Wi-Fi"
**Fix:** In development, DEBUG must be True. Or add your IP to `CAMPUS_WIFI_SUBNETS`.

### No rooms showing in sign-in form
**Fix:** Create rooms in Admin > Room section first.

### Peer search shows no results
**Fix:** Make sure other students are signed in and on campus network.

### Page says "PresenceSession" has no attribute
**Fix:** Run `python manage.py migrate` to create the table.

---

## 🎯 Common Workflows

### Workflow 1: Attendance Check-In
```
1. Student arrives on campus
2. Connects to University Wi-Fi
3. Opens CIS-Prox app
4. Clicks "Sign In"
5. Selects their location (Lab 1)
6. System confirms IP is on campus
7. Session created, student visible to peers
```

### Workflow 2: Peer Discovery
```
1. Student wants to find "Marco"
2. Goes to Peer Search
3. Types "Marco"
4. Sees: "Marco is in Laboratory 1 (25 min)"
5. Navigates to Lab 1 to meet Marco
```

### Workflow 3: End of Activity
```
1. Student finishes activity
2. Leaves campus or closes app
3. Manually clicks "Sign Out"
4. Session ends, location hidden
5. Admin sees session in history with duration
```

---

## 📞 Support

- **Django Docs**: https://docs.djangoproject.com/
- **Issues**: Check logs in Django admin
- **Admin Help**: See README.md for full documentation

---

**Version**: 1.0  
**Ready to Deploy**: Yes  
**Last Updated**: February 2, 2026
