# Django-Formset Migration Plan: Inline Photo Uploads

## Overview

Migrate offered and wanted book management from Django's `modelformset_factory` to django-formset, enabling inline photo uploads during book creation with temporary storage. Maintain 2:3 aspect ratio cropping for book covers.

## Problem statement

This is how it was originally phrased by the designer:

> the current implementation of this app has an offered book addition formset, that doesn't include cover image upoad, and a separate button in the profile view to upoload photos
> individually for each book after having created it. this turns out to be confusing for users, since they expect to find an upload photo button during book addition, and they miss the
> photo upload button in the profile.
>
> so I'm looking into alternatives to have that inline photo upload button while creating offered books. the current features are hard to merge, because the formset is processed server side
>  and the photo is ajax; bulk uploading the photos at the end would be problematic (what if some validation fails, what if it's too much to upload at once, etc), and I can't just make it
> ajax since the user may be adding a new book not yet submitted, so no db id to attach the new photo to before form submission.
>
> I saw that django-formset offers a solution for this type of problem.

## User Requirements

- ✅ Full django-formset migration for offered and wanted books
- ✅ Inline photo upload during book creation (before form submission)
- ✅ Maintain custom 2:3 crop, 400x600 thumbnails, 85% JPEG quality
- ✅ Wanted books remain text-only (no photos)
- ✅ Keep other forms (profile, auth) as traditional Django forms

## Implementation Phases

### Phase 1: Setup & Dependencies

**1.1 Install django-formset**
- Already installed (found in `.venv/lib/python3.14/site-packages/formset/`)
- Verify version: `uv run python -c "import formset; print(formset.__version__)"`
- Expected: 2.1.4 or newer

**1.2 Configure settings**
- File: `giralibros/settings/base.py`
- Add to `INSTALLED_APPS`: `'formset'` (check if already present)
- Configure temporary upload directory (uses `MEDIA_ROOT/upload_temp/` by default)
- Verify `MEDIA_ROOT` and `MEDIA_URL` are properly configured

**1.3 Add static files to templates**
- File: `books/templates/base_logged.html` (or appropriate base template)
- Add to `<head>` (after Bulma CSS):
  ```html
  {% load static %}
  {# Only need collections.css for form collections - NO framework-specific CSS needed #}
  <link href="{% static 'formset/css/collections.css' %}" rel="stylesheet">
  <script type="module" src="{% static 'formset/js/django-formset.js' %}"></script>
  ```
- Note: django-formset's Bulma integration augments your existing Bulma CSS, doesn't replace it
- The `collections.css` provides styles for add/remove collection buttons

### Phase 2: Migrate Offered Books (Without Photos First)

**2.1 Create new django-formset form**
- File: `books/forms.py`
- Create classes:
  ```python
  from formset.collection import FormCollection
  from formset.renderers.bulma import FormRenderer
  from django.forms import models

  class OfferedBookForm(models.ModelForm):
      """Individual book form within the collection."""
      default_renderer = FormRenderer()  # Enable Bulma integration

      class Meta:
          model = OfferedBook
          fields = ['title', 'author', 'notes']
          # FormRenderer will automatically add Bulma classes

  class OfferedBooksCollection(FormCollection):
      """Collection of offered book forms."""
      default_renderer = FormRenderer()  # Enable Bulma integration

      offered_book = OfferedBookForm()
      # Configure as collection with add/remove functionality
  ```
- Key: Use `FormRenderer()` from `formset.renderers.bulma` for automatic Bulma class application
- The renderer adds `.input`, `.textarea`, `.label` classes automatically
- No need for custom `BulmaFormMixin` - FormRenderer handles it

**2.2 Create new view with FileUploadMixin**
- File: `books/views.py`
- Create `OfferedBooksFormsetView` inheriting from:
  - `formset.upload.FileUploadMixin` (MUST be first for upload interception)
  - `LoginRequiredMixin`
  - `formset.views.EditCollectionView`
- Set `collection_class = OfferedBookDjFormset`
- Override `get_queryset()` to filter by `request.user`
- Override `form_collection_valid()` to handle user assignment and redirect
- Note: `FileUploadMixin` intercepts POST requests with multipart data for uploads

**2.3 Update URL routing**
- File: `giralibros/urls.py`
- Replace existing route: `path('my/offered/', views.OfferedBooksFormsetView.as_view(), name='my_offered')`
- Remove old `my_offered_books` function-based view

**2.4 Update template**
- File: `books/templates/my_offered_books.html` (replace existing)
- Structure:
  ```html
  {% extends "base_logged.html" %}

  {% block content %}
  <div class="columns is-centered">
    <div class="column is-full-mobile is-10-tablet is-8-desktop">
      <h1 class="title is-4 mb-2">Mis libros ofrecidos</h1>
      <p class="mb-4 has-text-grey">
        Agregá abajo los libros que tenés para cambiar...
      </p>

      <django-formset endpoint="{{ request.path }}" csrf-token="{{ csrf_token }}">
        {{ form_collection }}
      </django-formset>
    </div>
  </div>
  {% endblock %}
  ```
- Bulma container/column classes for wrapper only
- FormRenderer automatically renders forms with Bulma classes (`.box`, `.field`, `.control`, `.button`)
- django-formset's Bulma templates (`formset/bulma/form.html`, `formset/bulma/collection.html`) handle inner structure
- Remove `book_formset_manager.js` dependency - replaced by `django-formset.js`
- Test: Add, edit, delete books without photos

### Phase 3: Migrate Wanted Books (Text-Only)

**3.1 Create wanted books django-formset**
- File: `books/forms.py`
- Create `WantedBookDjFormset` similar to offered books
- Fields: `title`, `author` only (no notes, no photos)

**3.2 Create wanted books view**
- File: `books/views.py`
- Create `WantedBooksFormsetView` similar to offered books view
- NO `FileUploadMixin` needed (text-only)
- Inherits: `LoginRequiredMixin`, `formset.views.EditCollectionView`

**3.3 Update URL routing**
- File: `giralibros/urls.py`
- Replace: `path('my/wanted/', views.WantedBooksFormsetView.as_view(), name='my_wanted')`
- Remove old `my_wanted_books` function-based view

**3.4 Update template**
- File: `books/templates/my_wanted_books.html` (replace existing)
- Same `<django-formset>` wrapper structure
- Simpler rendering (no photo fields)

### Phase 4: Add Photo Upload to Offered Books

**4.1 Add ImageField to OfferedBookForm**
- File: `books/forms.py`
- Add to form fields:
  ```python
  from formset.widgets import UploadFileInput
  from formset.renderers.bulma import FormRenderer

  class OfferedBookForm(models.ModelForm):
      default_renderer = FormRenderer()  # Bulma integration

      class Meta:
          model = OfferedBook
          fields = ['title', 'author', 'notes', 'cover_image']
          widgets = {
              'cover_image': UploadFileInput(attrs={
                  'max-size': 5242880,  # 5MB
                  'accept': 'image/jpeg,image/png,image/webp',
              }),
          }
  ```
- The `UploadFileInput` will render using `formset/bulma/widgets/file.html` template
- Template includes Bulma button classes (`.button`, `.button.is-warning.is-small`, etc.)

**4.2 Understand upload flow**
1. User selects file → JS immediately POSTs to form endpoint (multipart)
2. `FileUploadMixin.post()` intercepts → `receive_uploaded_file()`
3. File saved to `MEDIA_ROOT/upload_temp/` with unique prefix
4. Returns JSON: `{"upload_temp_name": "<signed-path>", ...}`
5. User submits form → JSON with signed handle
6. `UploadFileInput.value_from_datadict()` unsigns, opens temp file
7. `CollectionFieldMixin.pre_serialize()` moves file to final location
8. Model saved with final file path

**4.3 Test basic photo upload**
- Upload photo during book creation
- Verify file moves from `upload_temp/` to `book_covers/`
- Verify `cover_image` field saved correctly
- Check `cover_uploaded_at` timestamp (may need custom save logic)

### Phase 5: Implement Custom Image Processing

**Problem**: Django-formset auto-generates 350x200 thumbnails but we need 2:3 crop, 400x600, 85% quality.

**5.1 Override receive_uploaded_file method**
- File: `books/views.py`
- In `OfferedBooksFormsetView`, override:
  ```python
  def receive_uploaded_file(self, request):
      # Call parent to handle temp storage
      response = super().receive_uploaded_file(request)

      # If it's a cover_image field, apply custom processing
      if 'cover_image' in request.FILES:
          # Get the uploaded file from temp storage
          # Apply EXIF correction, 2:3 crop, thumbnail resize
          # Replace temp file with processed version
          # Update response data if needed

      return response
  ```

**5.2 Extract current image processing logic**
- Source: `books/views.py:568-605` (current `upload_book_photo` view)
- Move to utility function: `_process_book_cover(image_file) -> BytesIO`
- Steps:
  1. Open with Pillow
  2. Apply `ImageOps.exif_transpose()`
  3. Convert to RGB if needed
  4. Calculate 2:3 aspect ratio crop
  5. Crop center
  6. Thumbnail to 400x600 max
  7. Save as JPEG 85% quality
  8. Return BytesIO object

**5.3 Apply processing in override**
- Open temp file from `default_storage`
- Process with `_process_book_cover()`
- Save processed version back to temp location
- Ensure signed handle remains valid

**Alternative Approach**: Process during final save
- Override `form_collection_valid()` in view
- After super().form_collection_valid(), iterate saved instances
- If `cover_image` changed, process and re-save
- Simpler but requires two saves per book with photo

### Phase 6: Handle cover_uploaded_at Timestamp

**6.1 Update timestamp on photo upload**
- File: `books/views.py`
- In `form_collection_valid()` override:
  ```python
  def form_collection_valid(self, form_collection):
      response = super().form_collection_valid(form_collection)

      # Update cover_uploaded_at for books with new photos
      for form in form_collection:
          instance = form.instance
          if instance.cover_image and not instance.cover_uploaded_at:
              instance.cover_uploaded_at = timezone.now()
              instance.save(update_fields=['cover_uploaded_at'])

      return response
  ```

### Phase 7: Bulma Integration Notes

**7.1 Built-in Bulma support**
- Django-formset's `FormRenderer()` automatically uses `formset/bulma/` templates:
  - `formset/bulma/form.html` - Form wrapper with `.box`
  - `formset/bulma/field_group.html` - Field containers with `.field`, `.control`
  - `formset/bulma/widgets/file.html` - File upload widget with `.button` classes
  - `formset/bulma/collection.html` - Collection with `.button.is-small.mb-2` for add/remove
- Widget classes automatically applied by FormRenderer:
  - Input fields: `.input`
  - Textareas: `.textarea`
  - Labels: `.label`
  - Buttons: `.button` with appropriate modifiers
- NO custom CSS needed unless user requests specific styling changes

**7.2 Optional: Override Bulma templates if needed**
- To customize: Create `templates/formset/bulma/widgets/file.html` in project
- Extends base template, override specific blocks
- Preserve Bulma classes to maintain consistency
- Only implement if user reports styling issues during manual testing

### Phase 8: Temporary File Cleanup

**8.1 Understand cleanup mechanism**
- Django-formset provides: `python manage.py cleanup_files --days=30`
- Deletes files older than 30 days in `upload_temp/`
- Time-based only (doesn't check if file is orphaned)

**8.2 Configure automated cleanup**
- Option 1: Cron job to run daily
- Option 2: Django-Q or Celery periodic task
- Option 3: Manual runs (simplest for now)
- Recommendation: Start with manual, add automation later

**8.3 Document cleanup process**
- Add to README or deployment docs
- Suggested schedule: Weekly runs with 7-day threshold
- Monitor `upload_temp/` directory size

**8.4 Consider edge cases**
- User uploads photo, then abandons form → Cleaned after timeout
- User uploads photo, validation fails → File stays in temp, retry succeeds
- Multiple users, concurrent uploads → Unique prefixes prevent collisions

### Phase 9: Backend Testing

**9.1 Identify existing tests**
- Search for tests of `my_offered_books` and `my_wanted_books` views
- Expected locations: `books/tests.py` or `books/tests/` directory
- Note current test patterns (Django TestCase, test client usage)

**9.2 Update tests for new views**
- Current tests expect traditional POST with form data
- Django-formset uses AJAX JSON submission
- Update test assertions to match new response format
- May need to simulate JSON POST or use django-formset test helpers
- Ensure tests still verify:
  - User can create/edit/delete books
  - Books are properly associated with user
  - Validation errors handled correctly

**9.3 Run test suite**
- Execute: `uv run python manage.py test`
- Verify all existing tests pass
- If tests fail, update test code (not production code) to match new backend

**9.4 Add minimal photo upload tests (backend only)**
- Test that photo field accepts valid image
- Test that `cover_uploaded_at` timestamp is set
- Test that temporary file is moved to final location
- Do NOT test UI interactions (drag/drop, progress, etc.) - user will test manually

### Phase 10: Final Cleanup

**10.1 Remove deprecated code**
- File: `books/views.py`
  - Remove `_manage_books()` function (lines 504-536)
  - Remove `upload_book_photo()` view (lines 540-644) - KEEP `_process_book_cover()` utility if moved to separate function
  - Old views removed when replacing with class-based views in Phase 2/3
- File: `books/templates/`
  - Remove `_book_form_entry.html` (no longer used)
  - Remove `upload_photo.html` (old upload page)
  - Templates replaced in Phase 2/3
- File: `books/static/js/`
  - Remove `book_formset_manager.js` (replaced by django-formset.js)
- File: `books/templates/profile.html`
  - Remove photo upload forms and AJAX handlers (lines 124-133, 270-358)
  - Photos now uploaded during book creation, not from profile

**10.2 Update navigation/links**
- Search for links to `my_offered` and `my_wanted` URLs
- Verify all redirects still work (URL names unchanged)
- Check templates referencing these views

**10.3 Data migration**
- No database schema changes required
- Existing `cover_image` field works with django-formset
- No migration needed

## Critical Files to Modify

### New Files
- None (all modifications to existing files)

### Modified Files
1. `giralibros/settings/base.py` - Add formset to INSTALLED_APPS
2. `books/templates/base_logged.html` - Load django-formset JS/CSS
3. `books/forms.py` - New django-formset form classes
4. `books/views.py` - New views with FileUploadMixin, custom processing
5. `giralibros/urls.py` - Update URL routing
6. `books/templates/my_offered_books.html` - Replace with django-formset template
7. `books/templates/my_wanted_books.html` - Replace with django-formset template

### Deleted Files (Phase 10)
- `books/templates/_book_form_entry.html` (shared partial no longer needed)
- `books/templates/upload_photo.html` (old upload page)
- `books/static/js/book_formset_manager.js` (replaced by django-formset.js)

## Key Architectural Decisions

### Why django-formset?
- Solves inline photo upload with temporary storage
- Pre-upload files before form submission
- Handles file cleanup via management command
- Bulma template support out of the box

### Custom Image Processing Strategy
- Override `receive_uploaded_file()` in view to apply processing during temp upload
- Preserves existing 2:3 crop logic for uniform book covers
- Alternative: Process during final save (simpler but two saves)

### Migration Strategy
- Direct replacement: No backward compatibility
- Incremental phases: Text-only forms first, photos second
- Test each phase before moving to next
- Tests updated to match new AJAX/JSON submission pattern

### Cleanup Strategy
- Start with manual `cleanup_files` runs
- Monitor temp directory growth
- Add automation later if needed
- 7-day threshold reasonable for book upload flow

## Testing Strategy

1. **Phase 2**: Run tests after offered books migration - update if needed
2. **Phase 3**: Run tests after wanted books migration - update if needed
3. **Phase 4**: Add basic photo upload backend test
4. **Phase 5**: Verify image processing in backend test
5. **Phase 9**: Comprehensive backend test review and updates
6. **Phase 10**: Final test run before cleanup

**Note**: User will manually test UI features (styling, UX, interactions)

## Risk Mitigation

If issues arise during implementation:
- Each phase is independently testable
- Git commits at each phase for reverting if needed
- No database migrations required (can revert code easily)
- Tests updated incrementally to catch regressions

## Success Criteria

- ✅ Users can add books and upload photos inline (single form)
- ✅ Photos maintain 2:3 aspect ratio with 400x600 thumbnails
- ✅ Temporary files cleaned automatically
- ✅ All existing tests pass with updated assertions
- ✅ Wanted books work text-only (no photo fields)
- ✅ Bulma styling consistent with existing design
- ✅ Mobile photo upload works (camera capture)
- ✅ Old separate photo upload code removed

## Open Questions / Future Enhancements

1. Should we add photo preview in formset before upload?
2. Multiple photos per book (gallery)?
3. Photo cropping UI for users to adjust crop?
4. Automated cleanup via cron vs manual?
5. Error recovery if temp file deleted before submission?

## Estimated Complexity

- **Phase 1-3**: Medium (django-formset learning curve)
- **Phase 4**: Low (add field with widget)
- **Phase 5**: Medium (custom processing integration)
- **Phase 6-8**: Low (timestamps, styling, cleanup)
- **Phase 9**: Medium (test updates)
- **Phase 10**: Low (cleanup)

**Overall**: Medium-High complexity due to framework migration, but incremental approach reduces risk.
