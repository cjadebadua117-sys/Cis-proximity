# Image Setup Instructions for CIS-Prox

## Logo Image (College of Information Systems Seal)

**File Location:** `media/logo-seal.png`

**Setup Instructions:**
1. Download or export the College of Information Systems seal image
2. Place it in the `media/` folder with the filename `logo-seal.png`
3. Ensure the image has a transparent background (PNG format recommended)
4. Recommended size: 500x500px or larger for crisp scaling
5. The logo will automatically scale to 50px height on desktop and 40px on mobile

**Expected Result:**
- Logo appears in the top-left corner of the header/navbar
- Text "CIS-Prox" and "Student Presence System" appear next to the logo
- Logo is responsive and scales properly on all devices

---

## Background Image (College of Information Systems Building)

**File Location:** `media/building.jpg`

**Setup Instructions:**
1. Download or export the College of Information Systems building photo
2. Place it in the `media/` folder with the filename `building.jpg`
3. Use JPG format for optimal file size
4. Recommended resolution: 1920x1080px or larger
5. The image will be:
   - Set as a full-width hero background on the home page
   - Covered with a 75% white/off-white faded overlay for readability
   - Fixed positioning on desktop (parallax effect), scrollable on mobile

**Expected Result:**
- Beautiful building image serves as the hero/header background
- Soft overlay ensures text remains readable and professional
- Responsive design works on all screen sizes
- Modern, university-quality appearance

---

## File Structure:

```
SWRS/
├── media/
│   ├── logo-seal.png          ← Place College seal here
│   ├── building.jpg           ← Place Building photo here
│   └── profile_pictures/
├── presence_app/
│   ├── static/
│   │   ├── style.css
│   │   └── images/
│   └── templates/
│       ├── base.html          ← References logo-seal.png
│       └── home.html          ← References building.jpg
└── swrs_config/
    └── settings.py            ← Static files configured
```

---

## Image Optimization Tips:

### Logo (logo-seal.png):
- Format: PNG with transparency
- Size: 500x500px minimum
- File size: < 200KB
- Background: Transparent or white

### Building (building.jpg):
- Format: JPEG (high quality)
- Size: 1920x1080px or larger
- File size: 200-500KB (balance quality with load time)
- Aspect ratio: 16:9 or similar

---

## Testing After Adding Images:

1. Place both images in the `media/` folder
2. Run Django development server: `python manage.py runserver`
3. Visit `http://localhost:8000` to see the home page
4. Verify:
   - Logo appears in header next to site title
   - Logo scales correctly on mobile (use DevTools)
   - Building image appears as hero background
   - Text is readable on top of the faded overlay
   - Layout looks professional on all screen sizes

---

## Responsive Behavior:

### Desktop (> 768px):
- Logo: 50px height, fixed ratio
- Building: Full-width, parallax scroll effect
- Overlay: 75% opacity (white #f5f5f7)

### Mobile (≤ 768px):
- Logo: 40px height, maintains aspect ratio
- Building: Full-width, standard scroll
- Overlay: Same 75% opacity, cleaner appearance
- Text remains centered and readable

---

## CSS References:

**Logo styling** (in base.html):
```css
.logo-img {
    height: 50px;
    width: auto;
    max-width: 50px;
    object-fit: contain;
    filter: brightness(1.1);
}
```

**Background styling** (in home.html):
```css
.hero-background {
    background-image: url('/media/building.jpg');
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
}

.hero-background::before {
    background: rgba(245, 245, 247, 0.75);
}
```

---

## Troubleshooting:

**Images not showing?**
1. Ensure file extensions are correct (.png for logo, .jpg for building)
2. Check that files are in the `media/` folder
3. Run `python manage.py collectstatic` (for production)
4. Clear browser cache (Ctrl+Shift+Delete or Cmd+Shift+Delete)
5. Check Django console for any image loading errors

**Logo stretched or distorted?**
- Ensure source image is square (500x500px)
- Check that `object-fit: contain` CSS is applied

**Building image loading slowly?**
- Optimize JPG file size (compress to 200-500KB)
- Use tools like TinyJPG or ImageOptim
- Consider using WebP format for better compression

**Text not readable on background?**
- Overlay opacity is set to 75% (#f5f5f7)
- Adjust in CSS if needed: `background: rgba(245, 245, 247, 0.70)` for lighter
- Change to `rgba(0, 0, 0, 0.3)` for darker overlay

