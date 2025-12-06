# Book Cover Photo Upload - Implementation Plan

## Statement of Requirements by App Designer

> The feature is for the users to optionally upload a cover photo of their book (of their actual physical book, that reflects not only edition but condition of the book).
>
> The way I imagine this would be that they would continue to use current offered books form, which is designed for lean bulk addition of books, but after adding them they could upload or take a photo (if on the phone) via a link or button in their list of offered books in their profile. the cover images would then be displayed as thumbnails in the scrollable list of books in the home page. this would make the app more attractive to users and incentivize more exchanges (it's more tempting to request an exchange if you've seen the book than just reading a title you may not even not know about).
>
> I would want to store only small-ish thumbnails not the full photo, so I expect some post processing, I suppose using pillow. the server has a few available gigas of storage so I could make it so that media is stored in the server and just the most recent N image (e.g. 1k) are ever kept to prevent running out of space. (e.g. via a cronjob that runs a management command; I don't want to add celery or something like that for background jobs---this should be operationally simple above all).
>
> The main concern I have right now is how would that look in the front end side of things. I use bulma and do server side rendering of templates, with inline vanilla js for some dynamicity. Is there a library or browser feature that would be a good fit for this? I imagine something where the user clicks the photo button and would allow either to upload a photo from disk or leverage the phone camera to take a picture.

---

## Feature Requirements

**Goal:** Allow users to optionally upload photos of their actual physical books to make the app more attractive and incentivize exchanges.

**Design Principles:**
- Minimalistic and operationally simple (suitable for VPS deployment)
- Server-side rendering with Bulma CSS and vanilla JavaScript
- No complex background job systems (no Celery)
- Cheap to run and maintain

**User Experience:**
- Users continue using current formset-based bulk book addition (`/my/offered/`)
- After books are created, users can upload photos from their profile page
- Upload button/link appears next to each offered book in profile
- Photos work on both mobile (camera) and desktop (file picker)
- Preview image before submitting (especially important for mobile photos)
- Thumbnails displayed in homepage's scrollable book list

**Technical Constraints:**
- Thumbnail size: ~400x600px, ~50-80KB per image
- Storage: Keep only N most recent images (e.g., 1000) to prevent running out of space
- Cleanup: Delete images when books are deleted + periodic cleanup via cron
- No external services (S3, Cloudinary, etc.)

---

## Frontend Implementation

### Photo Capture/Upload Interface

**Approach:** Native HTML5 file input with vanilla JavaScript preview

**HTML Input:**
```html
<input type="file" accept="image/*" capture="environment">
```

**How it works:**
- `accept="image/*"` - Only allow image files
- `capture="environment"` - On mobile, triggers camera directly (back camera)
- On desktop: Opens standard file picker
- Universal browser support (iOS Safari, Android Chrome, all modern browsers)

**JavaScript Preview Enhancement:**
- ~30 lines of vanilla JavaScript using `FileReader` API
- Shows preview thumbnail before user clicks "Save"
- Uses browser-native APIs (zero dependencies)
- Provides visual confirmation photo looks good before upload

**User Flow:**
1. Click "Add photo" button next to book in profile
2. **Mobile:** Camera opens → take photo → preview → save
3. **Desktop:** File picker opens → select image → preview → save
4. Server processes and stores thumbnail

**Why this approach:**
- Zero external JavaScript dependencies
- Users already familiar with this pattern (same as social media profile pics)
- Works perfectly on mobile and desktop
- Aligns with vanilla JS philosophy
- Simple to maintain

---

## Backend Implementation

### Dependencies

**Required:**
- **Pillow** - Image processing and thumbnail generation
  - Install: `uv add pillow`
  - Standard Django image handling library

**Recommended:**
- **django-cleanup** - Auto-deletes image files when models are deleted/updated
  - Install: `uv add django-cleanup`
  - Adds signal handler for automatic file cleanup (zero overhead)

### Django Configuration

**Settings changes (`giralibros/settings/base.py`):**
- Add `MEDIA_URL = '/media/'` - URL prefix for uploaded files
- Add `MEDIA_ROOT = BASE_DIR / 'media'` - Where files are stored on disk
- Production override: `/var/www/giralibros/media` (via environment variable)

**Installed apps:**
- Add `'django_cleanup.apps.CleanupConfig'` to `INSTALLED_APPS`

**URL configuration:**
- Development: Serve media files via Django
- Production: Configure nginx to serve `/media/` directory directly

### Model Changes

**OfferedBook model (`books/models.py`):**
- Add field: `cover_image = ImageField(upload_to='book_covers/%Y/%m/', blank=True, null=True)`
- Deprecate existing `cover_image` property (currently returns placeholder images)
- Create and run migration

**Storage organization:**
- Files stored in `media/book_covers/YYYY/MM/` (organized by upload date)
- Django auto-generates unique filenames

### View Changes

**New view:** `upload_book_photo(request, book_id)`
- Handle POST with multipart form data
- Validate: User owns book, file is valid image, reasonable size (<5MB)
- Process with Pillow:
  1. Open uploaded image
  2. Calculate aspect ratio
  3. Resize to max 400x600 (maintain proportions)
  4. Optimize quality (85-90% JPEG or WebP)
  5. Save to model's `cover_image` field
- Redirect back to profile

**Processing performance:**
- Synchronous processing (no background jobs needed)
- ~400x600px resize is fast (<1 second)
- Can optimize later if needed

**URL routing:**
- Add `/books/<int:book_id>/upload-photo/` endpoint

---

## Image Storage & Cleanup

### Dual Cleanup Strategy

**Strategy 1: Immediate deletion (django-cleanup)**
- Automatically deletes image file when book is deleted or image is replaced
- Uses Django signals - no manual code needed
- Storage freed immediately

**Strategy 2: Periodic cleanup (cron job)**
- Management command: `python manage.py cleanup_old_images`
- Keeps only N most recent images (e.g., 1000)
- Deletes orphaned files not referenced by any book
- Run weekly/monthly via cron: `0 3 * * 0 cd /path && uv run python manage.py cleanup_old_images`

**Why both:**
- Strategy 1 handles normal deletions
- Strategy 2 is safety net + enforces global storage limit

### Storage Capacity

**Math:**
- 50-80KB per thumbnail
- 1GB storage = ~12,000-20,000 images
- Limiting to 1,000 images = ~50-80MB total

---

## Template Changes

### Profile Template (`books/templates/profile.html`)

**Add to "Libros ofrecidos" section:**
- For each book without photo: "Add photo" button with camera icon
- For each book with photo: Show thumbnail + "Change photo" link
- Use FontAwesome camera icon (`fa-camera`)
- Button links to upload view

### Homepage Template (`books/templates/_book_list.html`)

**Book card layout:**
- Add image column using Bulma's `.media` component
- Display thumbnail on left, book info on right
- Fallback to existing placeholder images if no photo uploaded
- Maintain responsive design (mobile/desktop)

### Upload Interface

**Approach:** Dedicated upload page (can enhance to modal later)
- Navigate to `/books/{book_id}/upload-photo/`
- Simple form with file input + JavaScript preview
- Submit button to upload
- Redirect to profile after successful upload

---

## Implementation Phases

### Phase 1: Infrastructure Setup
1. Install Pillow: `uv add pillow`
2. Install django-cleanup: `uv add django-cleanup`
3. Update settings: Add MEDIA_ROOT, MEDIA_URL, django-cleanup to INSTALLED_APPS
4. Add ImageField to OfferedBook model
5. Create and run migration
6. Configure development server to serve media files

### Phase 2: Upload Functionality
1. Create `upload_book_photo` view with Pillow thumbnail generation
2. Add URL route for upload endpoint
3. Create upload template with file input
4. Add "Add photo" buttons to profile template

### Phase 3: Upload Preview
1. Add JavaScript preview (~30 lines) before upload using FileReader API
2. Test upload flow on mobile and desktop browsers
3. Verify thumbnail generation works correctly

### Phase 4: UI Display (Critical for Feature Success)
**Goal:** Make the book list visually attractive to drive user engagement

1. **Homepage book list (`_book_list.html`):**
   - Add image display to book cards using Bulma's `.media` component
   - Thumbnail on left, book info on right
   - Fallback to existing placeholder images if no photo uploaded
   - **Critical:** Get responsive layout right for both mobile and desktop
   - Test with various image aspect ratios

2. **Profile page display:**
   - Click to view photo (likely via modal using Bulma's `.modal` component)
   - Show thumbnail preview next to "Add photo" / "Change photo" buttons

3. **Search results:**
   - Ensure photo display works in search results (uses same `_book_list.html`)

4. **UI Polish:**
   - Ensure consistent spacing and alignment
   - Test on actual mobile devices
   - Verify loading performance with many images

**Note:** This phase is crucial - the feature's value depends on making the book list more appealing to users.

### Phase 5: Cleanup Management
1. Create `cleanup_old_images` management command
2. Test cleanup logic (delete orphaned files, keep N most recent)

### Phase 6: Production Setup
1. Configure nginx to serve media files
2. Set up cron job for periodic cleanup
3. Add media directory to backup strategy
4. Set appropriate file permissions on media directory

---

## Production Considerations

### review disk setup in the vps
- make sure the media dir is configured in a location that has enough space for planned usage
- limit allowed space such that the image upload feature fails but doesn't prevent the rest of the app from running as usual

### Nginx Configuration
- Serve `/media/` directory directly (bypass Django)
- Add cache headers for thumbnails (they don't change after creation)
- Set appropriate permissions on media directory

### Backup Strategy
- Include media directory in existing backup script
- Use rsync for media files backup

---

## Files to Modify

**Settings:**
- `giralibros/settings/base.py` - MEDIA_ROOT, MEDIA_URL, INSTALLED_APPS
- `giralibros/settings/production.py` - Production media path override

**Models:**
- `books/models.py` - Add ImageField to OfferedBook

**Views:**
- `books/views.py` - Add upload_book_photo view

**URLs:**
- `giralibros/urls.py` - Add upload photo endpoint

**Templates:**
- `books/templates/profile.html` - Add upload buttons
- `books/templates/_book_list.html` - Display thumbnails
- `books/templates/upload_photo.html` - New upload form template

**JavaScript:**
- Create `books/static/js/photo_preview.js` - Image preview before upload

**Management Commands:**
- `books/management/commands/cleanup_old_images.py` - New cleanup command

---

## Summary

**Complexity:** Low - follows standard Django patterns
**Dependencies:** Pillow + django-cleanup (both well-established)
**Operational overhead:** Minimal - one cron job
**External services:** None - everything on VPS
**Maintenance:** Standard Django/Pillow code, easy to maintain
