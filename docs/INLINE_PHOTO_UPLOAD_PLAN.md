# Inline Photo Upload for Offered Books Formset

## Problem Statement

The current implementation has separate flows for adding books and uploading photos:

1. **Book addition:** Users add/edit books via a formset at `/my/offered/` (server-side processing)
2. **Photo upload:** After saving books, users must find individual "Agregar foto" buttons on their profile page (AJAX upload)

**User confusion:**
- Users expect to find a photo upload button during book creation
- Users miss the photo upload buttons on the profile page
- The two-step process feels disconnected

**Technical challenges with merging the flows:**
- Formset is processed server-side
- Current photo upload is AJAX-based
- Bulk uploading photos at form submission is problematic (validation failures, large uploads)
- Can't use simple AJAX since new books don't have DB IDs yet to attach photos to

## Proposed Solution: Temporary Upload Directory

Inspired by django-formset's approach of using temporary storage for uploads before final form submission.

### Implementation Steps

1. **Add upload button to formset entries**
   - Similar button to profile page "Agregar/Cambiar foto"
   - One button per book form in the formset
   - Same take photo/upload file flow

2. **Create temporary upload endpoint**
   - Share image processing logic with existing `upload_book_photo` view
   - Instead of storing in OfferedBook.cover_image, save to temporary location
   - Use a TempBookCover model (recommended) for better guarantees
   - Return temp image reference (ID) to frontend

3. **Frontend state management**
   - JS attaches temp image ID to hidden field in the specific formset entry
   - Hidden field travels with the form through all operations (add/delete/reorder)

4. **Process temp images on form submission**
   - Formset view reads temp image references from hidden fields
   - Only after validation succeeds, copy/move temp images to OfferedBook instances
   - Delete temp files on successful upload
   - Handle missing temp files gracefully

5. **Cleanup cronjob**
   - Management command to delete temp files older than N hours/days
   - Prevents abandoned uploads from consuming disk space

## Initial Concerns (Analysis)

### 1. State Management Complexity - INITIALLY RATED HIGH ❌

**Initial concern:** Tracking which photo belongs to which formset entry when entries don't have DB IDs, especially when:
- User adds new entries dynamically
- Indices shift when entries are deleted
- Formset indices change when entries are reordered

**Why this was wrong:**
- Hidden fields automatically travel with their form elements
- Django's formset handles renaming fields when indices change
- When entry is deleted, hidden field is deleted with it
- No manual synchronization needed

**Actual complexity: LOW** ✅

### 2. Validation Error Flow - INITIALLY RATED HIGH ❌

**Initial concern:** When formset validation fails and form is re-rendered with errors:
- Need temp photo references to survive POST → error → re-render cycle
- Need to display photo previews for entries that had uploads
- Risk of losing photos when user fixes validation and resubmits

**Why this was wrong:**
- Hidden fields are included in POST data automatically
- Django formset reconstructs from POST, preserving hidden field values
- Temp image ID persists through validation errors
- Photo preview on error page is optional enhancement, not required

**Actual complexity: LOW** ✅

### 3. Security - INITIALLY RATED MEDIUM ⚠️

**Concern:** Temp uploads aren't immediately associated with a specific book:
- Can't verify ownership against a book (book doesn't exist yet)
- Need to prevent abuse, resource exhaustion, cross-user attacks

**Solution with TempBookCover model:**
```python
class TempBookCover(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='temp_book_covers/')
    created_at = models.DateTimeField(auto_now_add=True)
```

On formset submission, verify ownership:
```python
temp_cover = TempBookCover.objects.get(id=temp_cover_id, user=request.user)
```

**Actual complexity: LOW with model** ✅

### Other Minor Concerns

- **File I/O Performance:** Only happens after validation succeeds, not a bottleneck
- **Upload Race Conditions:** Can disable submit button while uploads in progress
- **JavaScript Complexity:** Reuse existing upload code from profile.html, adapt for formset
- **Mobile Camera Support:** `capture="environment"` should work fine per entry
- **Temp File Cleanup:** Standard management command pattern

## Revised Implementation Plan

### Database Changes

**1. Add TempBookCover model** (books/models.py)

```python
class TempBookCover(models.Model):
    """Temporary storage for book cover uploads before book is created."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='temp_book_covers/')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['created_at']),  # For cleanup queries
        ]
```

**2. Update OfferedBookForm** (books/forms.py)

```python
class OfferedBookForm(BulmaFormMixin, forms.ModelForm):
    temp_cover_id = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput()
    )

    class Meta:
        model = OfferedBook
        fields = ['title', 'author', 'notes']  # temp_cover_id handled separately
```

### Backend Changes

**3. Add temp upload endpoint** (books/views.py)

```python
@login_required
def upload_temp_book_photo(request):
    """
    Handle temporary book cover upload for books not yet created.
    Returns temp cover ID for client to store in formset hidden field.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    if "cover_image" not in request.FILES:
        return HttpResponseBadRequest("No image file provided")

    uploaded_file = request.FILES["cover_image"]

    # Validate file size and type (same as upload_book_photo)
    max_size = settings.BOOK_COVER_MAX_SIZE
    if uploaded_file.size > max_size:
        max_size_mb = max_size / (1024 * 1024)
        return HttpResponseBadRequest(
            f"Image file too large (max {max_size_mb:.0f}MB)"
        )

    allowed_types = settings.BOOK_COVER_ALLOWED_TYPES
    if uploaded_file.content_type not in allowed_types:
        return HttpResponseBadRequest("Invalid image format")

    try:
        # Process image (REUSE logic from upload_book_photo lines 568-615)
        image = Image.open(uploaded_file)
        image = ImageOps.exif_transpose(image) or image

        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        # Center crop to 2:3 aspect ratio
        target_aspect = 2 / 3
        img_width, img_height = image.size
        img_aspect = img_width / img_height

        if img_aspect > target_aspect:
            new_width = int(img_height * target_aspect)
            left = (img_width - new_width) // 2
            image = image.crop((left, 0, left + new_width, img_height))
        else:
            new_height = int(img_width / target_aspect)
            top = (img_height - new_height) // 2
            image = image.crop((0, top, img_width, top + new_height))

        # Create thumbnail
        max_width = settings.BOOK_COVER_THUMBNAIL_MAX_WIDTH
        max_height = settings.BOOK_COVER_THUMBNAIL_MAX_HEIGHT
        image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

        # Save to BytesIO
        output = BytesIO()
        quality = settings.BOOK_COVER_JPEG_QUALITY
        image.save(output, format="JPEG", quality=quality, optimize=True)
        output.seek(0)

        # Create InMemoryUploadedFile
        thumbnail = InMemoryUploadedFile(
            output,
            "ImageField",
            f"{uploaded_file.name.split('.')[0]}_thumb.jpg",
            "image/jpeg",
            output.getbuffer().nbytes,
            None,
        )

        # Save to TempBookCover
        temp_cover = TempBookCover(user=request.user)
        temp_cover.image.save(thumbnail.name, thumbnail, save=True)

        return JsonResponse({
            "success": True,
            "temp_cover_id": temp_cover.id,
            "image_url": temp_cover.image.url
        })

    except Exception as e:
        logger.error(f"Error processing temp image upload: {e}")
        return HttpResponseBadRequest("Error processing image")
```

**4. Update _manage_books view** (books/views.py)

```python
def _manage_books(request, book_model, book_form, template_name):
    """
    Generic view for managing user's books (offered or wanted).
    Now handles temporary photo uploads for new books.
    """
    BookFormSet = modelformset_factory(
        book_model,
        form=book_form,
        extra=1,
        can_delete=True,
    )

    queryset = book_model.objects.filter(user=request.user).order_by("created_at")

    if request.method == "POST":
        formset = BookFormSet(request.POST, queryset=queryset)
        if formset.is_valid():  # Validation happens first (failfast)
            instances = formset.save(commit=False)

            # Process each instance and its temp cover (if any)
            for instance, form in zip(instances, formset):
                if not instance.pk:
                    instance.user = request.user

                # Handle temp cover photo if present
                temp_cover_id = form.cleaned_data.get('temp_cover_id')
                if temp_cover_id:
                    try:
                        temp_cover = TempBookCover.objects.get(
                            id=temp_cover_id,
                            user=request.user  # Security: verify ownership
                        )
                        # Copy temp image to book's cover_image field
                        instance.cover_image = temp_cover.image
                        instance.cover_uploaded_at = timezone.now()
                        temp_cover.delete()  # Clean up immediately
                    except TempBookCover.DoesNotExist:
                        # Temp file missing - ignore gracefully
                        logger.warning(
                            f"TempBookCover {temp_cover_id} not found for user {request.user.id}"
                        )

                instance.save()

            for obj in formset.deleted_objects:
                obj.delete()

            return redirect("profile", username=request.user.username)
    else:
        formset = BookFormSet(queryset=queryset)

    return render(request, template_name, {"formset": formset})
```

**5. Add URL pattern** (giralibros/urls.py)

```python
path("upload-temp-photo/", views.upload_temp_book_photo, name="upload_temp_photo"),
```

### Frontend Changes

**6. Update formset template** (books/templates/_book_form_entry.html)

Add photo upload UI to each form entry:

```html
<div class="box book-entry {{ entry_class }}" {% if book_id %}data-book-id="{{ book_id }}"{% endif %}>
  <button type="button" class="delete delete-btn" aria-label="Eliminar" title="Borrar libro" tabindex="-1"></button>

  {# Hidden fields for formset #}
  {{ form.id }}
  {{ form.temp_cover_id }}  {# NEW: Hidden field for temp cover ID #}

  <div class="columns">
    <div class="column {% if not form.notes %}is-full{% endif %}">
      <div class="field">
        <input class="input" type="text" name="{{ form.title.html_name }}"
               id="{{ form.title.id_for_label }}"
               value="{{ form.title.value|default:'' }}"
               placeholder="Título del libro">
        {% if form.title.errors %}
          <p class="help is-danger">{{ form.title.errors.0 }}</p>
        {% endif %}
      </div>
      <div class="field">
        <input class="input" type="text" name="{{ form.author.html_name }}"
               id="{{ form.author.id_for_label }}"
               value="{{ form.author.value|default:'' }}"
               placeholder="Autor">
        {% if form.author.errors %}
          <p class="help is-danger">{{ form.author.errors.0 }}</p>
        {% endif %}
      </div>

      {# NEW: Photo upload section #}
      <div class="field">
        <input type="file"
               name="temp_cover_image"
               accept="image/*"
               capture="environment"
               style="display: none;"
               class="temp-photo-input"
               data-form-prefix="{{ form.prefix }}">
        <button type="button"
                class="button is-info is-small is-light temp-upload-trigger"
                data-form-prefix="{{ form.prefix }}">
          <span class="icon is-small">
            <i class="fas fa-camera"></i>
          </span>
          <span class="temp-upload-text">Agregar foto</span>
        </button>
        {# Photo preview area #}
        <div class="temp-photo-preview" data-form-prefix="{{ form.prefix }}" style="display: none; margin-top: 0.5rem;">
          <img src="" alt="Preview" style="max-width: 60px; max-height: 90px; border-radius: 4px;">
        </div>
      </div>
    </div>

    {% if form.notes %}
    <div class="column">
      {{ form.notes }}
      {% if form.notes.errors %}
        <p class="help is-danger">{{ form.notes.errors.0 }}</p>
      {% endif %}
    </div>
    {% endif %}
  </div>

  {# Hidden DELETE checkbox #}
  <div style="display: none;">
    {{ form.DELETE }}
  </div>
</div>
```

**7. Add JavaScript for temp uploads** (books/static/js/book_formset_manager.js)

Add to existing initBookFormset function:

```javascript
function initBookFormset(options) {
  const profileUrl = options.profileUrl;
  const tempUploadUrl = options.tempUploadUrl;  // NEW: Pass from template

  // ... existing code ...

  // NEW: Setup temp photo upload handlers
  function setupTempPhotoUploads() {
    // Trigger file input when button is clicked
    document.querySelectorAll('.temp-upload-trigger').forEach(button => {
      button.addEventListener('click', () => {
        const formPrefix = button.dataset.formPrefix;
        const fileInput = document.querySelector(
          `.temp-photo-input[data-form-prefix="${formPrefix}"]`
        );
        fileInput.click();
      });
    });

    // Handle file selection and upload
    document.querySelectorAll('.temp-photo-input').forEach(input => {
      input.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const formPrefix = input.dataset.formPrefix;
        const button = document.querySelector(
          `.temp-upload-trigger[data-form-prefix="${formPrefix}"]`
        );
        const preview = document.querySelector(
          `.temp-photo-preview[data-form-prefix="${formPrefix}"]`
        );
        const icon = button.querySelector('.icon i');
        const text = button.querySelector('.temp-upload-text');

        // Show loading state
        const originalIcon = icon.className;
        icon.className = 'fas fa-spinner fa-spin';
        button.disabled = true;

        try {
          // Upload via AJAX
          const formData = new FormData();
          formData.append('cover_image', file);

          const response = await fetch(tempUploadUrl, {
            method: 'POST',
            body: formData,
            headers: {
              'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
              'X-Requested-With': 'XMLHttpRequest'
            }
          });

          if (!response.ok) {
            throw new Error('Upload failed');
          }

          const data = await response.json();

          if (data.success) {
            // Store temp cover ID in hidden field
            const hiddenField = document.querySelector(
              `input[name="${formPrefix}-temp_cover_id"]`
            );
            hiddenField.value = data.temp_cover_id;

            // Show preview
            preview.querySelector('img').src = data.image_url;
            preview.style.display = 'block';

            // Update button text
            text.textContent = 'Cambiar foto';

            markDirty();
          } else {
            throw new Error(data.error || 'Upload failed');
          }
        } catch (error) {
          console.error('Upload error:', error);
          alert('Error al subir la foto. Por favor intentá de nuevo.');
        } finally {
          // Restore button state
          icon.className = originalIcon;
          button.disabled = false;
          input.value = '';  // Reset file input
        }
      });
    });
  }

  // Call after adding new entries
  function addNewEntry() {
    // ... existing code ...
    container.appendChild(newEntry);
    setupAutoAddEntry();
    setupDeleteButtons();
    setupChangeListeners(newEntry);
    setupTempPhotoUploads();  // NEW: Setup uploads for new entry
  }

  // Initialize
  setupAutoAddEntry();
  setupDeleteButtons();
  ensureEmptyEntry();
  setupTempPhotoUploads();  // NEW: Setup for existing entries

  // ... rest of existing code ...
}
```

**8. Update template script initialization** (books/templates/my_offered_books.html)

```javascript
<script>
document.addEventListener('DOMContentLoaded', () => {
  initBookFormset({
    profileUrl: "{% url 'profile' username=request.user.username %}",
    tempUploadUrl: "{% url 'upload_temp_photo' %}"  // NEW
  });
});
</script>
```

### Cleanup Management Command

**9. Add cleanup command** (books/management/commands/cleanup_temp_uploads.py)

```python
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from books.models import TempBookCover

class Command(BaseCommand):
    help = 'Delete temporary book cover uploads older than 24 hours'

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Delete temp files older than this many hours (default: 24)'
        )

    def handle(self, *args, **options):
        hours = options['hours']
        cutoff = timezone.now() - timedelta(hours=hours)

        deleted_count, _ = TempBookCover.objects.filter(
            created_at__lt=cutoff
        ).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully deleted {deleted_count} temporary cover(s) '
                f'older than {hours} hours'
            )
        )
```

**Setup cron job:**
```bash
# Run daily at 3 AM
0 3 * * * cd /path/to/giralibros && uv run python manage.py cleanup_temp_uploads
```

## Optional Enhancements

### Photo Preview on Validation Error

If validation fails, show previously uploaded photos:

```python
# In _manage_books view, before rendering on validation error:
if not formset.is_valid():
    # Attach temp cover image URLs for display
    for form in formset:
        temp_cover_id = form.data.get(f'{form.prefix}-temp_cover_id')
        if temp_cover_id:
            try:
                temp_cover = TempBookCover.objects.get(
                    id=temp_cover_id,
                    user=request.user
                )
                form.temp_cover_url = temp_cover.image.url
            except (TempBookCover.DoesNotExist, ValueError):
                pass

return render(request, template_name, {"formset": formset})
```

In template:
```html
{% if form.temp_cover_url %}
  <div class="temp-photo-preview" style="display: block;">
    <img src="{{ form.temp_cover_url }}" alt="Preview">
  </div>
{% endif %}
```

## Implementation Checklist

- [ ] Create TempBookCover model and migration
- [ ] Add temp_cover_id hidden field to OfferedBookForm
- [ ] Create upload_temp_book_photo view (reuse image processing logic)
- [ ] Add URL pattern for temp upload endpoint
- [ ] Update _manage_books to process temp covers after validation
- [ ] Update _book_form_entry.html template with upload button and preview area
- [ ] Add temp upload JavaScript to book_formset_manager.js
- [ ] Update my_offered_books.html to pass tempUploadUrl to JS
- [ ] Create cleanup management command
- [ ] Setup cron job for cleanup
- [ ] Test on mobile devices with camera
- [ ] Test validation error flow preserves temp photos
- [ ] Test deletion of entries with temp photos
- [ ] Consider: Add photo preview on validation error (optional)

## Testing Scenarios

1. **Happy path:** Add book, upload photo, submit successfully
2. **Validation error:** Upload photo, fail validation (missing title), fix and resubmit
3. **Multiple books:** Add 3 books with photos in single submission
4. **Delete entry:** Upload photo, then delete the book entry before submitting
5. **Reorder entries:** Add book A, add book B above it, verify photos stay with correct books
6. **Missing temp file:** Upload photo, wait for cleanup cron, submit form (should handle gracefully)
7. **Mobile camera:** Test camera capture on iOS and Android
8. **Cross-user security:** Verify User A can't attach User B's temp cover ID
9. **Abandoned upload:** Upload temp photo, navigate away without submitting, verify cleanup

## Advantages of This Approach

✅ **Clean state management:** Hidden fields automatically tracked by Django formset
✅ **Security:** TempBookCover model with user FK prevents cross-user attacks
✅ **Failfast validation:** Image processing only after form validation succeeds
✅ **Code reuse:** Share image processing logic between temp and permanent uploads
✅ **Graceful degradation:** Missing temp files handled without breaking form submission
✅ **User experience:** Photos can be uploaded during book creation, more intuitive
✅ **No race conditions:** Temp files persisted to DB before form submission

## Maintenance Considerations

- Monitor temp_book_covers directory size
- Adjust cleanup schedule if needed (currently 24 hours)
- Consider adding metrics for temp upload usage
- Could add DB index on TempBookCover.user_id if queries are slow


## My custom plan
1. add the TempBookCover model and migration
2. update the OfferedBookForm to include a hidden field that will reference the TempBookCover to be attached to a given book in the formset
3. update the book_form_entry formset template to include the hidden field when present (since this formset is reused for wanted books, this should be done conditionally like done for the form.notes field)
4. undo the _manage_books helper since we need wanted and offered books implementation to drift now.
5. after replicating the logic in my_offered_books and my_wanted_books and removing the helper, check the test still pass and wait for my review before proceeding.
6. update my_offered_books view to, after checking the form is valid abd doing instance processing, iterating over the forms and checking if the hidden field is set. if the field is set fetch the corresponding temp cover instance, copy its image data into the cover in the offered book, save and remove the original temp cover.
   - this is preferably done in a single transaction
   - this shouldn't erase cover fotos submitted on a previous post, but it should allow for covers to be updated while editing previously stored books

7. extract the image processing logic from upload_book_photo into a helper method

8. create a an upload_temp_book_photo ajax view that does similar work to upload_book_photo but creates a standalone TempBookCover instead of attaching an image field to an existing offered book

9. add an Agregar/Cambiar Foto button to each formin book_form_entry, with similar style/behavior as the one in profile view:
   - when clicked in mobile trigger taker photo
   - when clicked in desktop trigger file upload
   - when photo/upload is done, call the backend upload_temp_book_photo and use the result to populate the temp cover instance id in the hidden field for this form

10. at this point we should stop and let me manually test. we can work later on testing the feature and displaying the covers inline to the formset but not until we verify the parts connect as expected.
