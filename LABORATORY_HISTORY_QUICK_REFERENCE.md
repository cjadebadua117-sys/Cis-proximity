# Laboratory History - Quick Reference

## ðŸš€ Feature URLs

| Purpose | URL | Method | Auth Required |
|---------|-----|--------|---|
| View all lab history | `/laboratory/history/` | GET | Yes |
| Create new check-in | `/laboratory/checkin/` | GET/POST | Yes |
| Admin interface | `/admin/presence_app/laboratoryhistory/` | GET/POST | Staff Only |

---

## ðŸ“Š Database Schema

**Table:** `presence_app_laboratoryhistory`

```
id (Primary Key)
â”œâ”€â”€ student_id (FK â†’ auth_user)
â”œâ”€â”€ lab_room_number (CharField, max 20)
â”œâ”€â”€ entry_time (DateTimeField, auto-set)
â””â”€â”€ purpose_of_visit (TextField, max 500)
```

---

## ðŸŽ¨ Styling Summary

### Title (.lab-history-title)
```css
-webkit-text-stroke: 1.5px #FF00FF;  /* Magenta narrow stroke */
color: #ffffff;                      /* White text */
font-size: 2.5rem;
font-weight: 900;
```

### Color Palette
- **Magenta (Accent):** `#FF00FF`
- **Cyan (Student Names):** `#00ffff`
- **Green (Timestamps):** `#90EE90`
- **White (Text):** `#ffffff`
- **Dark Base:** `#1a1a1a`
- **Dark Secondary:** `#0a0a0a`
- **Light Gray:** `#e0e0e0`, `#b0b0b0`

---

## ðŸ”§ Implementation Checklist

- [x] **Model Created:** `LaboratoryHistory` with 4 fields
- [x] **Views Created:** `laboratory_history()` and `laboratory_checkin()`
- [x] **Templates Created:** `laboratory_history.html` and `laboratory_checkin.html`
- [x] **URLs Added:** 2 new routes in `urls.py`
- [x] **Navigation Updated:** "Lab History" link in `base.html`
- [x] **Admin Registered:** Control panel access for staff
- [x] **Migration Applied:** Database schema updated
- [x] **Styling Complete:** Dark theme with magenta neon title
- [ ] **Optional:** Add check-in button to dashboard (see below)

---

## ðŸ“‹ Optional: Add Dashboard Check-In Button

### Option 1: Simple Button Link
Add to `dashboard.html` in a suitable location:

```html
<div class="dashboard-quick-action">
    <h3>Lab Activities</h3>
    <a href="{% url 'laboratory_checkin' %}" class="btn btn-primary">
        âž• Check Into Lab
    </a>
</div>
```

### Option 2: Quick Check-In Modal (Without Leaving Dashboard)
Add to `dashboard.html`:

```html
<!-- Quick Lab Check-In Form -->
<div class="quick-checkin-container">
    <h3>Quick Lab Check-In</h3>
    <form method="POST" action="{% url 'laboratory_checkin' %}" class="quick-form">
        {% csrf_token %}
        <input 
            type="text" 
            name="lab_room_number" 
            placeholder="Lab Room (e.g., Lab-101)" 
            required
            class="form-control"
        >
        <textarea 
            name="purpose_of_visit" 
            placeholder="What are you doing?" 
            required
            class="form-control"
            rows="2"
        ></textarea>
        <button type="submit" class="btn btn-checkin">Check In</button>
    </form>
</div>
```

### Option 3: Card Component with Icon
```html
<div class="action-card">
    <div class="card-icon">ðŸ”¬</div>
    <h3>Lab Check-In</h3>
    <p>Record your laboratory visit</p>
    <a href="{% url 'laboratory_checkin' %}" class="btn btn-secondary">
        Start Check-In
    </a>
</div>
```

---

## ðŸ” View Permissions

| View | Requires Login | Requires Staff | Requires Permission |
|------|---|---|---|
| `laboratory_history` | âœ… Yes | âŒ No | âŒ No |
| `laboratory_checkin` | âœ… Yes | âŒ No | âŒ No |
| Admin Interface | âœ… Yes | âœ… Yes | âŒ No |

Both views are decorated with `@login_required` - only authenticated students can access.

---

## ðŸ“ Sample Data (for testing)

Insert test data via Django shell:

```python
python manage.py shell
```

```python
from django.contrib.auth.models import User
from presence_app.models import LaboratoryHistory
from django.utils import timezone

user = User.objects.first()  # Get any user

# Create test entry
lab = LaboratoryHistory.objects.create(
    student=user,
    lab_room_number="Lab-101",
    purpose_of_visit="Programming assignment - Part 1"
)

print(f"Created: {lab}")

# Query examples
all_labs = LaboratoryHistory.objects.all()
print(f"Total entries: {all_labs.count()}")

user_labs = user.lab_visits.all()
print(f"User's visits: {user_labs.count()}")

lab_101_entries = LaboratoryHistory.objects.filter(lab_room_number="Lab-101")
print(f"Lab-101 entries: {lab_101_entries.count()}")
```

---

## ðŸ› Troubleshooting

### Migration Issues
```bash
# Reset migrations (development only!)
python manage.py migrate presence_app zero
python manage.py migrate

# Or just reapply
python manage.py migrate presence_app
```

### Clear Stale Sessions
```bash
python manage.py clearsessions
```

### Verify Installation
```bash
python manage.py check  # Should show "System check identified no issues"
```

---

## ðŸ“‚ File Map

```
CIS-proximity/
â”œâ”€â”€ presence_app/
â”‚   â”œâ”€â”€ models.py                                    # Added LaboratoryHistory
â”‚   â”œâ”€â”€ views.py                                     # Added 2 views
â”‚   â”œâ”€â”€ admin.py                                     # Registered model
â”‚   â”œâ”€â”€ templates/
â”‚   â”‚   â”œâ”€â”€ base.html                                # Updated nav
â”‚   â”‚   â”œâ”€â”€ laboratory_history.html                  # NEW - Logbook display
â”‚   â”‚   â””â”€â”€ laboratory_checkin.html                  # NEW - Check-in form
â”‚   â””â”€â”€ migrations/
â”‚       â””â”€â”€ 0009_laboratoryhistory.py                # Database migration
â”œâ”€â”€ swrs_config/
â”‚   â””â”€â”€ urls.py                                      # Added 2 URL paths
â””â”€â”€ LABORATORY_HISTORY_GUIDE.md                      # Complete documentation
```

---

## ðŸŽ¯ Common Tasks

### View all lab entries
```
GET /laboratory/history/
```

### Check into a lab
```
GET /laboratory/checkin/  (Form page)
POST /laboratory/checkin/ (Submit form)
```

### Manage from admin
```
GET/POST /admin/presence_app/laboratoryhistory/
```

### Get user's lab visits in code
```python
user.lab_visits.all()  # Returns QuerySet of LaboratoryHistory
```

### Filter by lab room
```python
from presence_app.models import LaboratoryHistory
LaboratoryHistory.objects.filter(lab_room_number="Lab-101")
```

### Export to CSV (Django shell)
```python
import csv
from presence_app.models import LaboratoryHistory

with open('lab_history.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Student', 'Lab Room', 'Entry Time', 'Purpose'])
    for entry in LaboratoryHistory.objects.all():
        writer.writerow([
            entry.student.username,
            entry.lab_room_number,
            entry.entry_time,
            entry.purpose_of_visit
        ])
```

---

## âœ¨ Feature Highlights

1. **Zero Configuration** - Ready to use immediately after migration
2. **Clean Neon Styling** - Matches your system's aesthetic with magenta text-stroke
3. **Dark Theme** - Modern, professional appearance
4. **Responsive Design** - Works on desktop and mobile
5. **Secure** - Login required, linked to User accounts
6. **Queryable** - Easy to generate reports and analytics
7. **Admin Interface** - Full CRUD operations for staff

---

## ðŸ“ž Support

For implementation help, see `LABORATORY_HISTORY_GUIDE.md` for detailed documentation.

**Created:** February 9, 2026  
**Status:** âœ… Production Ready

