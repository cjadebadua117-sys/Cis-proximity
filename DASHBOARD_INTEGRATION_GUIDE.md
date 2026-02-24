# Dashboard Integration Guide

This guide shows how to add the Laboratory Check-In button to your main dashboard.

## Current Dashboard Location
File: `presence_app/templates/dashboard.html`

## Option 1: Simple Button (Recommended)

Find your dashboard main content area and add this code:

```html
<!-- Laboratory Check-In Quick Action -->
<div style="margin-top: 2rem;">
    <h3 style="color: #FF00FF; font-weight: 600; margin-bottom: 1rem;">Lab Access</h3>
    <div style="display: flex; gap: 1rem;">
        <a href="{% url 'laboratory_checkin' %}" class="btn btn-checkin" 
           style="padding: 0.9rem 1.8rem; background: linear-gradient(135deg, #FF00FF, #FF1493); 
                  color: #fff; border: none; border-radius: 6px; font-weight: 600; 
                  cursor: pointer; text-decoration: none; box-shadow: 0 0 20px rgba(255, 0, 255, 0.3);
                  transition: all 0.3s ease;">
            ➕ Check Into Lab
        </a>
        <a href="{% url 'laboratory_history' %}" class="btn btn-history"
           style="padding: 0.9rem 1.8rem; background: transparent; border: 1px solid #FF00FF; 
                  color: #FF00FF; border-radius: 6px; font-weight: 600; cursor: pointer; 
                  text-decoration: none; transition: all 0.3s ease;">
            📋 View History
        </a>
    </div>
</div>
```

## Option 2: Card Component

For a more modern card-based design:

```html
<!-- Lab Tracking Card -->
<div style="background: #1a1a1a; border: 1px solid #333; border-radius: 12px; 
            padding: 1.5rem; margin-top: 2rem; box-shadow: 0 4px 15px rgba(0,0,0,0.3);">
    <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;">
        <span style="font-size: 2rem;">🔬</span>
        <div>
            <h3 style="color: #FF00FF; margin: 0; font-size: 1.2rem;">Laboratory Access</h3>
            <p style="color: #888; margin: 0.5rem 0 0 0; font-size: 0.9rem;">Track your lab visits automatically</p>
        </div>
    </div>
    <a href="{% url 'laboratory_checkin' %}" 
       style="display: inline-block; padding: 0.8rem 1.5rem; background: linear-gradient(135deg, #FF00FF, #FF1493); 
              color: #fff; border: none; border-radius: 6px; font-weight: 600; font-size: 0.95rem;
              cursor: pointer; text-decoration: none; box-shadow: 0 0 15px rgba(255, 0, 255, 0.3);
              transition: all 0.3s ease;">
        Check In to Lab
    </a>
</div>
```

## Option 3: Inline Quick Check-In Form

To allow check-in without leaving the dashboard:

```html
<!-- Quick Lab Check-In - Inline Form -->
<div style="background: #1a1a1a; border: 1px solid #333; border-radius: 12px; 
            padding: 1.5rem; margin-top: 2rem;">
    <h3 style="color: #FF00FF; margin-top: 0;">Quick Lab Check-In</h3>
    <form method="POST" action="{% url 'laboratory_checkin' %}" style="display: flex; gap: 1rem; flex-wrap: wrap;">
        {% csrf_token %}
        
        <input type="text" 
               name="lab_room_number" 
               placeholder="Lab Room (e.g., Lab-101)" 
               required
               style="flex: 1; min-width: 150px; padding: 0.8rem; 
                      background: #0a0a0a; border: 1px solid #333; 
                      border-radius: 6px; color: #e0e0e0; font-size: 0.95rem;">
        
        <textarea name="purpose_of_visit" 
                  placeholder="Purpose (e.g., Assignment work)" 
                  required
                  style="flex: 1; min-width: 200px; padding: 0.8rem; 
                         background: #0a0a0a; border: 1px solid #333; 
                         border-radius: 6px; color: #e0e0e0; font-size: 0.95rem;
                         resize: none; height: 2.5rem;"></textarea>
        
        <button type="submit" 
                style="padding: 0.8rem 1.5rem; background: linear-gradient(135deg, #FF00FF, #FF1493); 
                       color: #fff; border: none; border-radius: 6px; font-weight: 600; 
                       cursor: pointer; white-space: nowrap;">
            Check In
        </button>
    </form>
</div>
```

## Option 4: Tabbed Interface

If your dashboard has multiple sections, add as a tab:

```html
<!-- Add to your dashboard tabs -->
<div class="dashboard-tab" id="lab-tab">
    <div style="padding: 1.5rem;">
        <h2 style="color: #FF00FF; margin-top: 0;">Laboratory History</h2>
        
        <a href="{% url 'laboratory_checkin' %}" class="btn btn-primary" 
           style="margin-bottom: 1.5rem; padding: 0.8rem 1.5rem; 
                  background: linear-gradient(135deg, #FF00FF, #FF1493); 
                  color: #fff; border: none; border-radius: 6px; 
                  font-weight: 600; cursor: pointer; text-decoration: none;">
            ➕ New Check-In
        </a>
        
        <!-- Embed latest entries (optional) -->
        <!-- You could add a view to show latest 5 entries here -->
    </div>
</div>
```

## HTML Placement Guide

**Good locations to add the check-in button:**

1. **After Welcome Section**
   ```
   ┌─────────────────────┐
   │  Welcome Message    │
   ├─────────────────────┤
   │  LAB CHECK-IN       │ ← Add here
   ├─────────────────────┤
   │  Other Dashboard    │
   │  Sections           │
   └─────────────────────┘
   ```

2. **In a Sidebar**
   ```
   Main Content      | Quick Actions
                     | - Check In Lab
                     | - View History
                     | - Other
   ```

3. **At the Top (Prominent)**
   Make it the first thing students see after login.

## Adding to Your dashboard.html

Here's the exact location to find and modify:

```html
<!-- In presence_app/templates/dashboard.html -->

{% extends 'base.html' %}
{% load static %}

{% block content %}
<div class="dashboard-container">
    
    <!-- Existing Welcome Section -->
    <h1>Welcome, {{ user.get_full_name|default:user.username }}!</h1>
    
    <!-- ADD YOUR CHECK-IN SECTION HERE -->
    <div style="background: #1a1a1a; border: 1px solid #333; border-radius: 12px; 
                padding: 1.5rem; margin: 1.5rem 0;">
        <h3 style="color: #FF00FF; margin-top: 0;">Laboratory Access</h3>
        <a href="{% url 'laboratory_checkin' %}" class="btn btn-primary">
            Check Into Lab
        </a>
    </div>
    
    <!-- Existing Dashboard Content -->
    {% block dashboard_content %}
    <!-- Your existing sections... -->
    {% endblock %}
    
</div>
{% endblock %}
```

## With Styling

If you want to match your dashboard theme exactly, add a CSS class:

### In your HTML:
```html
<a href="{% url 'laboratory_checkin' %}" class="btn btn-lab-checkin">
    ➕ Check Into Lab
</a>
```

### In `style.css` (or inline `<style>` tag):
```css
.btn-lab-checkin {
    display: inline-block;
    padding: 0.9rem 1.8rem;
    background: linear-gradient(135deg, #FF00FF, #FF1493);
    color: #fff;
    border: none;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.95rem;
    cursor: pointer;
    text-decoration: none;
    box-shadow: 0 0 20px rgba(255, 0, 255, 0.3);
    transition: all 0.3s ease;
    letter-spacing: 0.5px;
}

.btn-lab-checkin:hover {
    box-shadow: 0 0 40px rgba(255, 0, 255, 0.6);
    transform: translateY(-2px);
}

.btn-lab-checkin:active {
    transform: translateY(0);
}

@media (max-width: 768px) {
    .btn-lab-checkin {
        width: 100%;
        text-align: center;
    }
}
```

## Dynamic Check-In Count (Advanced)

Show how many times a user has checked in:

```html
<div style="display: flex; gap: 2rem; margin: 1.5rem 0;">
    <div>
        <div style="font-size: 2rem; color: #FF00FF; font-weight: 900;">
            {{ user.lab_visits.count }}
        </div>
        <div style="color: #888; font-size: 0.9rem;">Lab Check-Ins</div>
    </div>
    <div>
        <div style="font-size: 2rem; color: #90EE90; font-weight: 900;">
            {% if user.lab_visits.first %}
                {{ user.lab_visits.first.entry_time|date:"H:i" }}
            {% else %}
                —
            {% endif %}
        </div>
        <div style="color: #888; font-size: 0.9rem;">Latest Check-In</div>
    </div>
</div>

<a href="{% url 'laboratory_checkin' %}" class="btn btn-lab-checkin">
    ➕ Check In Now
</a>
```

## Testing

After adding the button:

1. Log in to dashboard
2. Verify button appears
3. Click to test it opens `/laboratory/checkin/`
4. Fill in lab room and purpose
5. Submit and verify redirect to history
6. Check that entry appears in the logbook

## Next Steps

- [ ] Copy one of the code snippets above
- [ ] Paste into your `dashboard.html` in appropriate location
- [ ] Test the button functionality
- [ ] Adjust styling to match your dashboard theme
- [ ] Deploy to production

---

**Note:** These code snippets use inline styles for easy copy-paste. For production, move styles to your `style.css` or `neon.css` file.
