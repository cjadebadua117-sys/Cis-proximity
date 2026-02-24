# CIS-Prox System - Quick Start Guide

## Current Status ✓

Your CIS-Prox system is fully functional and ready for image integration:

- ✓ Django application configured
- ✓ Database migrations applied
- ✓ Views and routes working
- ✓ Static files configured
- ✓ Templates updated with logo and background structure
- ✓ Media directory ready for images

---

## What You Need to Do (3 Simple Steps)

### Step 1: Add the Images

Place these two files in your `media/` folder:

1. **logo-seal.png** - College of Information Systems Seal
   - Format: PNG with transparent background
   - Recommended size: 500x500px
   - Destination: `c:\Users\Admin\Desktop\SWRS\media\logo-seal.png`

2. **building.jpg** - College of Information Systems Building
   - Format: JPG (or PNG)
   - Recommended size: 1920x1080px
   - Destination: `c:\Users\Admin\Desktop\SWRS\media\building.jpg`

**Current media folder contents:**
- `media/profile_pictures/` (for user profile images - already configured)
- `media/` (ready for logo-seal.png and building.jpg)

### Step 2: Start the Development Server

Open a terminal in your project folder and run:

```bash
python manage.py runserver
```

You'll see output like:
```
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

### Step 3: Test the Website

1. Open your browser to: `http://localhost:8000`
2. **Verify:**
   - Logo appears in top-left corner of header
   - Building image is visible as background on home page
   - Text is readable on top of the background
   - Works on mobile (resize browser to test)

---

## Expected Results After Adding Images

### Home Page (http://localhost:8000)
- **Hero Section:** Large building photo with soft faded overlay
- **Title:** "CIS-Prox System"
- **Subtitle:** "Network-Authenticated Student Presence & Real-Time Indoor Locating"
- **Visual:** Professional university aesthetic

### Header (All Pages)
- **Logo:** College seal image (50px height)
- **Text:** "CIS-Prox" with subtitle "Student Presence System"
- **Navigation:** Links to Dashboard, Activity Hours, Profile, Sign Out
- **Responsive:** Logo scales down on mobile devices

### Mobile Responsiveness
- **Tablet (768px-1024px):** All elements properly scaled
- **Mobile (< 768px):** 
  - Logo: 40px height
  - Background: Standard scroll (not parallax)
  - Text remains readable and centered

---

## File Structure

After adding images, your folder structure will be:

```
c:\Users\Admin\Desktop\SWRS\
├── media/
│   ├── logo-seal.png          ← Add this
│   ├── building.jpg           ← Add this
│   └── profile_pictures/
├── presence_app/
│   ├── static/
│   │   └── style.css
│   ├── templates/
│   │   ├── base.html
│   │   ├── home.html
│   │   ├── dashboard.html
│   │   ├── ... (other templates)
│   └── migrations/
├── swrs_config/
├── manage.py
└── db.sqlite3
```

---

## Image Paths in Code

The system references your images at:

1. **Logo in Header** (base.html):
   ```html
   <img class="logo-img" src="/media/logo-seal.png" alt="CIS Seal">
   ```

2. **Background Image** (home.html):
   ```css
   background-image: url('/media/building.jpg');
   ```

These paths tell Django to serve the images from your `media/` folder.

---

## CSS Styling Reference

### Logo Styling:
```css
.logo-img {
    height: 50px;                    /* Desktop size */
    width: auto;
    max-width: 50px;
    object-fit: contain;
    filter: brightness(1.1);         /* Slight brightness boost */
}

@media (max-width: 768px) {
    .logo-img {
        height: 40px;                /* Mobile size */
    }
}
```

### Background Overlay:
```css
.hero-background {
    background-image: url('/media/building.jpg');
    background-size: cover;          /* Covers entire area */
    background-position: center;     /* Centered */
    background-attachment: fixed;   /* Parallax on desktop */
}

.hero-background::before {
    background: rgba(245, 245, 247, 0.75);  /* 75% white overlay */
}

@media (max-width: 768px) {
    .hero-background {
        background-attachment: scroll;      /* Normal scroll on mobile */
    }
}
```

---

## Troubleshooting

### Images not showing?

**Problem:** Logo or background image is missing/broken
- ✓ Check file names are exactly: `logo-seal.png` and `building.jpg`
- ✓ Check files are in the `media/` folder
- ✓ Check file paths use forward slashes: `/media/logo-seal.png`
- ✓ Restart the development server
- ✓ Clear browser cache (Ctrl+Shift+Delete)

**Problem:** Images load slowly
- ✓ Reduce file size (compress JPG to 200-500KB)
- ✓ Use web-optimized images (1920x1080px is good)
- ✓ Try: https://tinyjpg.com or ImageOptim

**Problem:** Logo looks stretched or pixelated
- ✓ Ensure source image is square (500x500px minimum)
- ✓ Use PNG format for logo (crisp graphics)

**Problem:** Text not readable on background
- ✓ Adjust overlay opacity in CSS (currently 0.75 = 75%)
- ✓ Change `rgba(245, 245, 247, 0.75)` to `0.85` for darker
- ✓ Or use `rgba(0, 0, 0, 0.3)` for darker overlay with building showing through

---

## Image Optimization Tips

### For the Logo (logo-seal.png):
- Use PNG with transparency
- Size: 500x500px (square recommended)
- File size: < 200KB
- Tools: Photoshop, GIMP, or online PNG optimizer

### For the Building (building.jpg):
- Use JPEG format (smaller file size)
- Size: 1920x1080px (16:9 aspect ratio)
- File size: 200-500KB (balance quality)
- Tools: TinyJPG.com, ImageOptim, or Photoshop

---

## Advanced Options

### Adjust Overlay Brightness
Edit home.html `<style>` section:

```css
/* Lighter overlay (show more building) */
.hero-background::before {
    background: rgba(245, 245, 247, 0.6);  /* 60% instead of 75% */
}

/* Darker overlay (easier text reading) */
.hero-background::before {
    background: rgba(0, 0, 0, 0.3);        /* Dark overlay */
}
```

### Add Parallax on Mobile
Change home.html media query:

```css
@media (max-width: 768px) {
    .hero-background {
        background-attachment: fixed;  /* Keep parallax on mobile */
    }
}
```

### Change Logo Brightness
Edit base.html `<style>` section:

```css
.logo-img {
    filter: brightness(1.0);  /* Normal brightness */
    /* or */
    filter: brightness(0.8);  /* Darker logo */
}
```

---

## Summary

Your CIS-Prox system is **100% ready**. Just add the two images to the `media/` folder and you're done!

The system is configured to:
- ✓ Serve images from `/media/` directory
- ✓ Display logo in responsive header
- ✓ Show building as hero background with faded overlay
- ✓ Provide professional university aesthetic
- ✓ Work perfectly on mobile and desktop

**Next step:** Add `logo-seal.png` and `building.jpg` to your `media/` folder, then test!

For detailed image setup instructions, see: `IMAGE_SETUP.md`

