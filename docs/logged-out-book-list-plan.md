# Plan: Show Book List to Logged-Out Users

## Summary
Allow logged-out users to preview the book list before registering, while hiding private information (username, notes). This improves user acquisition by giving potential users a preview of available books before committing to registration.

## Initial designer request

```
this is a django app for book exchanges. the current implementation reveals almost no info to logged out users, prompting with a register form
 by default and offering an option to log in. the problem is this way potential users have no preview of the content before registering, which
may drive them away. So I want to show the book list to logged out users as well, while not revealing much info about users.

the main challenge is that I don't want to add much complexity to the view and template, so I want to be smart about it.

as part of this change, I think we also need to move away of register being the default redirect on logged out users. It's weird because by
using redirect we lose the ?next= functionality (since for registering an email verification flow is needed). Login is better ux.
```

## Requirements
1. Logged-out users see book list at `/` (same URL as logged-in)
2. Infinite scroll works for both auth states
3. No search UI for logged-out users (backend logic can remain)
4. No location filtering for logged-out users (show all books)
5. Replace header with "Registrate o iniciá sesión" CTA
6. Hide username from book cards
7. **Hide notes from book cards**
8. "Cambio" button redirects to login (with login icon)
9. **Disable modal click (or redirect to login)**
10. Change `LOGIN_URL` from "register" to "login"

## Proposed Architecture

To avoid maintaining 4 versions (desktop logged-in, mobile logged-in, desktop logged-out, mobile logged-out), we'll use a **single book card template** and **single home template** with conditionals:

```
OfferedBookManager.for_user(user)
  ├── If authenticated: filter by locations, annotate already_requested
  └── If anonymous: all books, dummy already_requested annotation

_book_card.html (new)
  ├── Contains: desktop layout, mobile layout, modal
  └── Uses: conditional logic based on request.user.is_authenticated

_book_list.html (modified to be just a loop)
  └── Loops over books, includes _book_card.html

home.html (modified, adds logged-out heading)
  ├── If not authenticated: show CTA heading with register/login buttons
  ├── If authenticated: existing search/filter/default headings
  └── Includes _book_list.html
```

This ensures:
- **Single source of truth** for card styling (Bulma classes)
- **No duplication** across desktop/mobile or page structure/JavaScript
- **Clean separation** of concerns: manager handles querysets, card handles display, home handles headings
- **Minimal conditionals** justified by preventing 4+ template versions
- **Easy to maintain** - style/logic changes only in one place

## Implementation Steps

**Important Notes:**
- **No automatic commits:** The agent CANNOT create git commits. Human review and approval is required after completing each commit-size step before proceeding to the next.
- **Testing:** Test cases are provided for documentation purposes only. The human developer will stub test cases for implementation - do not add test cases without explicit approval per CLAUDE.md rules.

### Commit 1: Change LOGIN_URL setting
**File:** `giralibros/settings/base.py`

Change:
```python
LOGIN_URL = "register"
```
To:
```python
LOGIN_URL = "login"
```

**Rationale:** Better UX - login preserves `?next=` parameter (though not using it for Cambio button, good for future features). Registration requires email verification which breaks the redirect flow.

---

### Commit 2: Create shared `_book_card.html` template
**File:** `books/templates/_book_card.html` (new)

Extract the card HTML from current `_book_list.html` into a reusable component that:
- Takes `book` object from context
- Contains both desktop (`.is-hidden-mobile`) and mobile (`.is-hidden-tablet`) layouts
- Contains modal structure
- Uses conditionals based on `request.user.is_authenticated`:
  - If logged out: hide username, hide notes, disable author search links, show login button with `fa-right-to-bracket` icon, disable modal onclick
  - If logged in: show all fields, enable AJAX exchange button, enable modal onclick

**Structure:**
```django
{% load static %}
{% load book_filters %}

<div class="column is-full-mobile is-one-third-tablet is-one-quarter-desktop is-one-fifth-widescreen">
  <div class="card">
    <!-- Desktop/Tablet: Vertical layout -->
    <div class="card-content is-hidden-mobile">
      <div class="book-cover-container mb-3 has-text-centered"
           {% if request.user.is_authenticated %}style="cursor: pointer;" onclick="document.getElementById('modal-{{ book.id }}').classList.add('is-active')"{% endif %}>
        <!-- Cover image/placeholder -->
      </div>
      <p class="is-size-6 mb-1"><strong>{{ book.title }}</strong></p>
      <p class="is-size-6 mb-2">
        {% if request.user.is_authenticated %}
          <a href="{% url 'home' %}?search={{ book.author|urlencode }}" ...>{{ book.author }}</a>
        {% else %}
          <span class="has-text-grey-dark">{{ book.author }}</span>
        {% endif %}
      </p>

      {% if book.notes and request.user.is_authenticated %}
        <p class="is-size-7 mb-2 has-text-grey" ...>{{ book.notes }}</p>
      {% endif %}

      <div style="margin-top: auto;">
        <div class="mb-2 is-flex is-justify-content-space-between is-align-items-baseline">
          {% if request.user.is_authenticated %}
            <!-- Username link -->
          {% endif %}
          <!-- Timestamp (always show) -->
        </div>

        {% if not request.user.is_authenticated %}
          <a href="{% url 'login' %}" class="button is-primary is-fullwidth" title="Iniciar sesión para solicitar intercambio">
            <span class="icon"><i class="fas fa-right-to-bracket"></i></span>
            <span>Cambio</span>
          </a>
        {% elif book.user != request.user %}
          {% include '_exchange_button.html' with button_classes='is-fullwidth' %}
        {% endif %}
      </div>
    </div>

    <!-- Mobile: Horizontal layout (similar structure with request.user.is_authenticated conditionals) -->
    ...

    <!-- Modal (only if authenticated) -->
    {% if request.user.is_authenticated %}
      <div id="modal-{{ book.id }}" class="modal">
        ...
      </div>
    {% endif %}
  </div>
</div>
```

---

### Commit 3: Refactor `_book_list.html` to use `_book_card.html`
**File:** `books/templates/_book_list.html`

Replace entire content with:
```django
{% load static %}
{% load book_filters %}
<div class="columns is-multiline">
{% for book in offered_books %}
  {% include '_book_card.html' with book=book %}
{% endfor %}
</div>
```

**This is a refactor** - logged-in functionality should remain identical, just moved to `_book_card.html`. The `_book_card.html` handles auth state internally via `request.user.is_authenticated`.

---

### Commit 4: Update `OfferedBookManager.for_user` to handle AnonymousUser
**File:** `books/models.py` (OfferedBookManager class, around lines 100-124)

Modify `for_user()` method to handle unauthenticated users:

```python
def for_user(self, user):
    """
    Return books available to the user.
    For authenticated users: filter by user's locations and annotate already_requested.
    For anonymous users: return all books with no location filtering.
    """
    if user.is_authenticated:
        # Existing logic: filter by location and annotate
        user_areas = user.locations.values_list("area", flat=True)

        queryset = (
            self.filter(user__locations__area__in=user_areas)
            .select_related("user")
            .prefetch_related("user__locations")
            .distinct()
        )

        queryset = self._annotate_last_activity(queryset)
        queryset = queryset.order_by("-last_activity_date")

        return self._annotate_already_requested(queryset, user)
    else:
        # Anonymous users: all books, no location filtering, no already_requested annotation
        from django.db.models import Value, BooleanField

        queryset = (
            self.all()
            .select_related("user")
            .prefetch_related("user__locations")
        )

        queryset = self._annotate_last_activity(queryset)
        queryset = queryset.order_by("-last_activity_date")

        # Add dummy already_requested annotation for template compatibility
        return queryset.annotate(already_requested=Value(False, output_field=BooleanField()))
```

**Rationale:** Encapsulates the anonymous user logic in the manager where it belongs, keeping the view clean.

---

### Commit 5: Modify `list_books` view for unauthenticated access
**File:** `books/views.py` (lines 223-291)

Changes:
1. **Remove** `@login_required` decorator
2. **Add** auth check for profile redirect:
   ```python
   if request.user.is_authenticated:
       if not hasattr(request.user, "profile"):
           return redirect("profile_edit")
   ```
3. **Simplify** queryset logic (manager now handles anonymous users):
   ```python
   offered_books = OfferedBook.objects.for_user(request.user)
   ```

4. **Wrap** wanted filter in auth check:
   ```python
   if search_query:
       offered_books = OfferedBook.objects.search(offered_books, search_query)
   elif filter_wanted and request.user.is_authenticated:
       offered_books = OfferedBook.objects.filter_by_wanted(offered_books, request.user)
   ```

5. Keep pagination/AJAX logic unchanged (works for both states)
6. Ensure `request=request` passed to `render_to_string` in AJAX handler

---

### Commit 6: Update `home.html` heading for logged-out users
**File:** `books/templates/home.html` (lines 5-29)

Add a new conditional clause at the beginning of the heading logic to show CTA for logged-out users:

```django
<div class="mb-5 has-text-centered" style="margin-top: -1rem">
  {% if not user.is_authenticated %}
  {# Logged-out users: show CTA #}
  <h1 class="title is-5">📚 GiraLibros</h1>
  <p class="subtitle is-6 has-text-grey mb-3">
    La comunidad gratuita de intercambio de libros en Buenos Aires
  </p>
  <div class="buttons is-centered">
    <a href="{% url 'register' %}" class="button is-primary">Registrate</a>
    <a href="{% url 'login' %}" class="button is-light">Iniciá sesión</a>
  </div>
  {% elif search_query %}
  {# Existing search results heading #}
  ...
  {% elif filter_wanted %}
  {# Existing wanted filter heading #}
  ...
  {% else %}
  {# Existing default heading #}
  ...
  {% endif %}
</div>

{# Skip "no offered books" warning for logged-out users #}
{% if user.is_authenticated and not user.offered.exists %}
<div class="columns is-centered">
  ...
</div>
{% endif %}
```

**Rationale:** Single `home.html` template with conditional heading. No duplication of JavaScript or page structure. Consistent with existing conditionals in `_book_card.html`.

---

## Files Modified/Created

### Modified Files
1. `giralibros/settings/base.py` - Change LOGIN_URL
2. `books/models.py` - Update OfferedBookManager.for_user to handle AnonymousUser
3. `books/views.py` - Remove @login_required, simplify queryset (manager handles it)
4. `books/templates/_book_list.html` - Refactor to simple loop using _book_card.html
5. `books/templates/home.html` - Add logged-out heading conditional, wrap warning check

### New Files
1. `books/templates/_book_card.html` - Shared card component (checks request.user.is_authenticated)

### Not Modified (confirmed safe)
1. `books/templates/profile.html` - Uses separate book display layout (lines 108-152), not affected
2. `books/templates/_exchange_button.html` - Still used by logged-in cards
3. `books/templates/base_logged.html` - Still used by logged-in home.html

## Potential Issues & Solutions

### Issue 1: Template context in AJAX responses
When rendering `_book_list.html` via AJAX, need to ensure `request.user` is available for auth checks in `_book_card.html`.

**Solution:** Pass `request=request` to `render_to_string()` in the AJAX handler.

### Issue 2: Maintaining style consistency
With `_book_card.html` as single source, risk is conditionals make it hard to read.

**Solution:** Use clear `{% if request.user.is_authenticated %}` blocks with comments explaining what's hidden/shown. Keep conditionals minimal - only around username, notes, author links, button, and modal. The conditionals are justified by preventing 4 separate templates.

### Issue 3: Testing coverage
Need to verify both auth states work correctly with pagination and AJAX.

**Recommended test cases (for human to stub):**
- Logged-out users can access `/` without redirect
- Logged-out users see all books (no location filtering)
- Pagination works for logged-out users
- AJAX infinite scroll works for logged-out users
- Logged-out users don't see username/notes in rendered HTML
- Logged-out "Cambio" button redirects to `/login/`
- Logged-in behavior unchanged (location filtering, exchange button, modal)
- OfferedBookManager.for_user handles AnonymousUser correctly

## Summary

**6 commits, 5 modified files, 1 new file:**
1. Settings: LOGIN_URL change
2. Template: Extract `_book_card.html` with auth conditionals
3. Template: Simplify `_book_list.html` to loop
4. Model: Make `OfferedBookManager.for_user` handle AnonymousUser
5. View: Remove @login_required, simplify (manager does the work)
6. Template: Add logged-out heading to `home.html`

**Architecture benefits:**
- Single source for card styling (no 4-way split)
- Single source for page structure/JS (no template duplication)
- Manager encapsulates queryset logic
- Conditionals justified and minimal
