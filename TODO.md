# Lab History Bug Fix Plan

## Issue Analysis

### Root Cause:
1. **Instructor has no section assigned**: The instructor "haber" has `Section = None`, causing the lab history query `filter(student__studentpresence__section=section)` to return empty results
2. **Multiple unsigned-out sessions**: Student has multiple sign-in records without sign-out times, which can cause the sign_out view to pick wrong records

## Fix Plan

### Fix 1: laboratory_history view
- Add handling for instructors with no section assigned
- Show all lab history for staff/superusers
- Show helpful message for instructors without section

### Fix 2: sign_out view  
- Fix the query to get the correct sign-in record (oldest unsigned-out first, not latest)
- Ensure proper lab history creation

### Fix 3: Add user feedback
- Add appropriate error messages when section is not assigned
