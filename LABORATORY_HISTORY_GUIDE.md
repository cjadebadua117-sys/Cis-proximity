# Laboratory History Feature - Implementation Guide

## Overview
The Laboratory History feature is a digital logbook system that replaces physical attendance records for laboratory usage. It allows students to check in when entering a lab and maintains a complete audit trail of all lab visits with timestamps and purpose information.

---

## What Was Created

### 1. Database Model (models.py)
**Model Name:** `LaboratoryHistory`

```python
class LaboratoryHistory(models.Model):
    """
    Digital logbook for laboratory visits.
    Tracks student entries to replace physical attendance logbook.
    """
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lab_visits')
    lab_room_number = models.CharField(max_length=20, help_text="e.g., Lab-101, Lab-202")
    entry_time = models.DateTimeField(auto_now_add=True)
    purpose_of_visit = models.TextField(max_length=500, help_text="What is the student doing in the lab?")
```

**Fields:**
- **student**: Foreign key to User model - automatically captures who checked in
- **lab_room_number**: Text field for lab identifier (e.g., "Lab-101", "CIS-Lab")
- **entry_time**: Auto-timestamped when record is created (most recent entries at top)
- **purpose_of_visit**: Text field for student to explain their lab activity

**Key Features:**
- Automatically ordered by most recent entries first (`ordering = ['-entry_time']`)
- Accessible as `user.lab_visits` for related queries

---

### 2. Views (views.py)

#### View 1: Laboratory History Display
```python
@login_required
def laboratory_history(request):
    """
    Display Laboratory History (digital logbook) with all lab visits.
    Sorted by most recent entries first.
    """
    lab_history = LaboratoryHistory.objects.all().order_by('-entry_time')
    context = {
        'lab_history': lab_history,
        'total_entries': lab_history.count(),
    }
    return render(request, 'laboratory_history.html', context)
```

**Purpose:** Displays the digital logbook with all lab check-ins  
**Route:** `/laboratory/history/`  
**Template:** `laboratory_history.html`

#### View 2: Laboratory Check-In
```python
@login_required
def laboratory_checkin(request):
    """
    Handle check-in to laboratory. Creates a new LaboratoryHistory record.
    Can be called via POST from dashboard with lab_room_number and purpose_of_visit.
    """
    if request.method == 'POST':
        lab_room = request.POST.get('lab_room_number')
        purpose = request.POST.get('purpose_of_visit')
        
        if lab_room and purpose:
            LaboratoryHistory.objects.create(
                student=request.user,
                lab_room_number=lab_room,
                purpose_of_visit=purpose
            )
            messages.success(request, f'Successfully checked in to {lab_room}!')
            return redirect('laboratory_history')
        else:
            messages.error(request, 'Please provide both lab room and purpose.')
    
    return render(request, 'laboratory_checkin.html')
```

**Purpose:** Handles student check-in to labs  
**Route:** `/laboratory/checkin/`  
**Template:** `laboratory_checkin.html`

---

### 3. Templates

#### Template 1: laboratory_history.html
**File Location:** `presence_app/templates/laboratory_history.html`

**Features:**
- **Magenta Neon Title:** Uses `-webkit-text-stroke: 1.5px #FF00FF` for narrow magenta stroke effect
- **Dark Digital Logbook Design:** Black background (#1a1a1a) with #333 borders
- **Modern Table Layout:**
  - Magenta header row with cyan student names
  - Green timestamps for readability
  - Hover effects with magenta glow
  - Responsive design for mobile
- **Stats Bar:** Shows total entries and latest check-in time
- **Empty State:** Helpful message when no records exist
- **Check-In Button:** Direct link to check-in form with gradient magenta styling

**Color Scheme:**
- Title: Magenta (#FF00FF) with white stroke
- Headers: Magenta text on dark background
- Student names: Cyan (#00ffff)
- Lab rooms: Magenta (#FF00FF)
- Timestamps: Green (#90EE90)
- Purpose text: Light gray (#b0b0b0)
- Buttons: Magenta gradient with glow effect

#### Template 2: laboratory_checkin.html
**File Location:** `presence_app/templates/laboratory_checkin.html`

**Features:**
- **Clean Card Design:** Centered form with dark theme
- **Magenta Title:** Matching the neon aesthetic
- **Form Fields:**
  - Lab Room Number (text input)
  - Purpose of Visit (textarea)
- **Validation:** HTML5 required fields
- **Actions:** Submit and Back buttons
- **Error Handling:** Displays success/error messages

---

### 4. URL Configuration (urls.py)

**Update Location:** `swrs_config/urls.py`

**Added Routes:**
```python
# Laboratory History (Digital Logbook)
path('laboratory/history/', views.laboratory_history, name='laboratory_history'),
path('laboratory/checkin/', views.laboratory_checkin, name='laboratory_checkin'),
```

**Access URLs:**
- View History: `http://localhost:8000/laboratory/history/`
- Check In: `http://localhost:8000/laboratory/checkin/`

---

### 5. Navigation Integration (base.html)

**Updated:** `presence_app/templates/base.html`

Added navigation link for authenticated students:
```html
<li><a href="/laboratory/history/" class="nav-link accent {% if '/laboratory' in request.path %}active{% endif %}">Lab History</a></li>
```

The link appears in the main navigation menu for all authenticated non-instructor users.

---

### 6. Django Admin Interface

**Updated:** `presence_app/admin.py`

Registered `LaboratoryHistory` with admin interface:

```python
@admin.register(LaboratoryHistory)
class LaboratoryHistoryAdmin(admin.ModelAdmin):
    list_display = ('student', 'lab_room_number', 'entry_time', 'purpose_preview')
    list_filter = ('lab_room_number', 'entry_time')
    search_fields = ('student__username', 'student__email', 'lab_room_number')
    readonly_fields = ('entry_time', 'student')
    ordering = ['-entry_time']
```

**Features:**
- Search by student username/email or lab room
- Filter by lab room and entry date
- Read-only student and timestamp fields (prevent accidental changes)
- Purpose text preview in list view

**Access:** `http://localhost:8000/admin/presence_app/laboratoryhistory/`

---

## How to Use

### For Students

1. **View Lab History:**
   - Click "Lab History" in the navigation menu
   - See all your laboratory visits sorted by most recent first
   - View who else has been in which lab

2. **Check In to Lab:**
   - Click the "+ Check-In" button on the Laboratory History page
   - Fill in:
     - **Lab Room:** The lab location (e.g., "Lab-101", "CIS-Lab")
     - **Purpose:** What you're doing (e.g., "Programming assignment", "Study group", "Project development")
   - Click "Check In"
   - Your entry is recorded with automatic timestamp

### For Instructors/Admins

1. **View All Lab History:**
   - Go to Django Admin: `/admin/`
   - Navigate to "Laboratory History"
   - View all student lab visits
   - Search by student or lab room
   - Filter by date range or specific labs

2. **Generate Reports:**
   - Use Django ORM to query: `LaboratoryHistory.objects.filter(lab_room_number='Lab-101')`
   - Export data for auditing purposes

---

## Next Steps - Adding Dashboard Check-In Button

To add a quick check-in button to your main dashboard, update your `dashboard.html` template:

```html
<!-- Add this section in your dashboard template -->
<div class="quick-actions">
    <h3>Quick Actions</h3>
    <a href="{% url 'laboratory_checkin' %}" class="btn btn-checkin">
        Check In to Lab
    </a>
</div>
```

Or create a quick-check-in modal that doesn't leave the dashboard:

```html
<form method="POST" action="{% url 'laboratory_checkin' %}" style="display: inline;">
    {% csrf_token %}
    <input type="text" name="lab_room_number" placeholder="Lab Room (e.g., Lab-101)" required>
    <textarea name="purpose_of_visit" placeholder="What are you doing?" required></textarea>
    <button type="submit" class="btn btn-checkin">Check In</button>
</form>
```

---

## Styling Details

### Magenta Neon Text Stroke
The Laboratory History title uses a **narrow magenta stroke** (1.5px) for a sharp "piping" effect:

```css
.lab-history-title {
    -webkit-text-stroke: 1.5px #FF00FF; /* Sharp magenta edge */
    color: #ffffff; /* White center */
    text-shadow: 1px 0 0 #FF00FF, -1px 0 0 #FF00FF, /* Fallback outline */
                 0 1px 0 #FF00FF, 0 -1px 0 #FF00FF;
}
```

This matches your system's neon aesthetic (like "Student Presence System" in the header) but with magenta (#FF00FF) instead of blue.

### Dark Theme Colors
- **Background:** #1a1a1a (near black)
- **Borders:** #333 (dark gray)
- **Headers:** #0a0a0a (pure black)
- **Text:** #e0e0e0 (light gray)
- **Accents:** #FF00FF (magenta), #00ffff (cyan), #90EE90 (green)

---

## Database Migration

The migration `0009_laboratoryhistory.py` has been applied. The database schema includes:

- **Table:** `presence_app_laboratoryhistory`
- **Columns:**
  - id (Primary Key)
  - student_id (Foreign Key to User)
  - lab_room_number (CharField, 20 chars)
  - entry_time (DateTimeField, auto-set)
  - purpose_of_visit (TextField, 500 chars)

---

## Troubleshooting

### Issue: 404 error on laboratory history page
**Solution:** Ensure migrations were applied: `python manage.py migrate`

### Issue: "Laboratory History" doesn't appear in navigation
**Solution:** Check that the user is authenticated and not an instructor. The link only shows for students.

### Issue: Can't access Django Admin for Laboratory History
**Solution:** Ensure you're logged in as a staff user and the model was registered in `admin.py` (already done).

### Issue: Timestamps are in wrong timezone
**Solution:** Configure `TIME_ZONE` in `settings.py` to your local timezone.

---

## Summary of Changes Made

| Component | File | Changes |
|-----------|------|---------|
| **Model** | `models.py` | Added `LaboratoryHistory` model with 4 fields |
| **Views** | `views.py` | Added 2 views: `laboratory_history()` and `laboratory_checkin()` |
| **Templates** | New files | Created `laboratory_history.html` and `laboratory_checkin.html` |
| **URLs** | `urls.py` | Added 2 URL paths for the feature |
| **Admin** | `admin.py` | Registered `LaboratoryHistory` with custom admin interface |
| **Navigation** | `base.html` | Added "Lab History" link to student navigation |
| **Migration** | New file | Created `0009_laboratoryhistory.py` migration |

---

## Feature Highlights

✅ **Automatic Timestamps** - Entry time captured automatically  
✅ **Student Linking** - Records link to User accounts  
✅ **Neon Styling** - Magenta text stroke matching your system aesthetic  
✅ **Dark Theme** - Modern digital logbook appearance  
✅ **Search & Filter** - Admin interface with search and filtering  
✅ **Responsive Design** - Works on mobile devices  
✅ **Authentication** - Login required to prevent unauthorized access  
✅ **Audit Trail** - Complete history of all lab visits  

---

## Testing the Feature

1. **Create Test Data:**
   ```python
   python manage.py shell
   from django.contrib.auth.models import User
   from presence_app.models import LaboratoryHistory
   
   user = User.objects.first()
   LaboratoryHistory.objects.create(
       student=user,
       lab_room_number="Lab-101",
       purpose_of_visit="Test check-in"
   )
   ```

2. **Access the Pages:**
   - Visit `/laboratory/history/` to view the logbook
   - Visit `/laboratory/checkin/` to test check-in form
   - Check Django Admin at `/admin/presence_app/laboratoryhistory/`

3. **Verify Styling:**
   - Check that title has magenta stroke (1.5px)
   - Verify dark theme colors match your design
   - Test responsive design on mobile

---

**Feature Status:** ✅ Complete and Ready to Use

For questions or customizations, refer to the inline code comments or Django documentation.
