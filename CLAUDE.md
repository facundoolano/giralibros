# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Giralibros is a Django-based book exchange platform where users can offer books for exchange and request books from other users. The system includes location-based filtering (focused on Buenos Aires areas) and manages exchange requests between users.

## Development Commands

**Note**: This project uses `uv` for dependency management. All Python commands should be run with `uv run` prefix (e.g., `uv run python manage.py`).

### Environment Setup
```bash
# Install dependencies
uv sync

# Install dev dependencies
uv sync --group dev
```

### Database Management
```bash
# Run migrations
uv run python manage.py migrate

# Create migrations after model changes
uv run python manage.py makemigrations

# Load sample/test data from fixtures
uv run python manage.py loaddata sample_books

# Create superuser for admin access
uv run python manage.py createsuperuser
```

### Running the Application
```bash
# Start development server
uv run python manage.py runserver

# Admin interface available at http://localhost:8000/admin/
```

### Testing and Type Checking
```bash
# Run tests
uv run python manage.py test --settings=giralibros.settings.test

# Type checking with mypy (django-stubs configured)
uv run mypy .
```

## Architecture

### Core Models (books/models.py)

The application uses a relational model centered around users and books:

- **UserProfile**: Extended user information including contact preferences and about section
- **UserLocation**: Geographic areas where users are willing to exchange (CABA, GBA Norte/Oeste/Sur)
- **OfferedBook** / **WantedBook**: Both inherit from abstract BaseBook (title, author, created_at)
  - OfferedBook: Books users have available, can be marked as reserved
  - WantedBook: Books users are searching for
- **ExchangeRequest**: Denormalized exchange requests between users with book details stored directly to handle book deletions

### Location System

The platform uses LocationArea choices for Buenos Aires metropolitan area:
- CABA (Ciudad Autónoma de Buenos Aires)
- GBA_NORTE (Greater Buenos Aires North)
- GBA_OESTE (Greater Buenos Aires West)
- GBA_SUR (Greater Buenos Aires South)

Users can have multiple locations via UserLocation ForeignKey relationship, affecting which books they see from other users.

### Key Design Decisions

1. **Denormalized ExchangeRequest**: Stores book title/author directly rather than ForeignKey to handle cases where offered books are deleted after request is made
2. **to_user uses SET_NULL**: Allows ExchangeRequest to persist even if target user is deleted
3. **BaseBook abstraction**: Shared fields (title, author, created_at) between offered and wanted books
4. **Reserved flag**: OfferedBook has a 'reserved' boolean to mark pending exchanges without removing the book from the database

## Project Structure

```
giralibros/            # Django project configuration
  settings.py          # Django settings (SQLite database, installed apps)
  urls.py             # URL routing (currently only admin)

books/                 # Main application
  models.py           # All data models
  admin.py            # Admin interface configuration
  views.py            # View logic (currently empty)
  migrations/         # Database migrations
  fixtures/           # Test/sample data fixtures
    sample_books.json # Sample users, locations, and books
```

## Django Configuration

- **Database**: SQLite (db.sqlite3)
- **Python Version**: >= 3.14
- **Django Version**: >= 4.2.26
- **Settings Module**: giralibros.settings
- **Installed Apps**: Standard Django apps + 'books'
- **Admin Interface**: Enabled at /admin/

## Type Checking

The project uses django-stubs for type checking. Configuration in pyproject.toml:
```toml
[mypy.plugins.django-stubs]
django_settings_module = "giralibros.settings"
```

## Testing Philosophy

### Core Principles

The goal of testing is to **catch bugs and prevent regressions**. Tests should focus on observable behavior that matters to users, not implementation details.

### Preferred Testing Approach

1. **Favor integration tests over unit tests**: Test Django views with real HTTP requests and database interactions using Django's `TestCase` (which provides transaction isolation)
2. **Test business logic through behavior**: Focus on meaningful user actions (creating exchange requests, filtering by location, reserving books) rather than testing individual model methods in isolation
3. **Use the real database**: Never mock Django's ORM or database; use Django's test database
4. **Minimize mocking**: Only mock external services (email, third-party APIs). Don't mock internal collaborators or model relationships
5. **Keep tests simple**: Use helper functions to reduce duplication, but avoid complex test abstractions or frameworks

### What to Test

- **Critical business flows**: Exchange request creation, location-based filtering, book reservation logic
- **Edge cases**: Handling deleted books in exchange requests, user deletion with SET_NULL, location overlap scenarios
- **Simple models**: Test through views/integration tests rather than isolated unit tests

### What NOT to Test

- Django framework behavior (URL routing, ORM functionality)
- Simple CRUD operations without business logic
- Implementation details (internal method calls, private functions)
- Every single code path (coverage is informative, not a target)

### Test Implementation Rules (for AI assistants)

When working with tests:
- **Don't add new test cases** unless explicitly requested
- **Skip incomplete test specifications**: If a test has placeholders like "FIXME human to provide spec", skip implementing it
- **Don't skip tests**: Run the full test suite; don't use markers to skip failing tests
- **Discuss before adjusting code for tests**: If a test requires changing production code, discuss the approach first rather than immediately modifying the code to make tests pass
- **Use docstrings**: Every test method should have a one-sentence docstring explaining the use case or business rule being tested (e.g., "Test that a user is redirected to profile setup on first login")
- **Propose tests for new business logic**: When adding new features with business rules, propose test cases (with FIXME placeholders for specs) for the human to review and fill in, but don't implement them without permission
- **No direct database access in client tests**: Tests using Django's test client should only check observable application behavior (status codes, redirects, response content, outbound emails). Don't directly access the database to verify state (e.g., `User.objects.get()`, checking model attributes). The only exception is helper methods with explicit FIXME notes for temporary workarounds.

## Code Style

### Comments and Docstrings

1. **No redundant comments**: Don't write comments that simply restate what the code does. Comments should explain *why*, not *what*.
2. **Function docstrings**:
   - Considered part of the public interface
   - Should be succinct and focus on behavior
   - Don't duplicate information already in the function signature
   - Don't refer to implementation details—describe what callers care about
   - Example: Instead of "Renders both .txt and .html versions of the template and sends a multipart email", write "Send multipart email with HTML and plain text versions"

## Frontend & Styling

- **CSS Framework**: Bulma (https://bulma.io/documentation/)
- **Icons**: FontAwesome
- **JavaScript**: Vanilla JS (no frameworks)

**Important**: Leverage Bulma as much as possible for layout and styling. Do not create custom CSS components or inline styles for things already handled by Bulma. Refer to the Bulma documentation when building UI components to use the appropriate classes and modifiers.
