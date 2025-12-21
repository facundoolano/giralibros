# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Giralibros is a Django-based book exchange platform where users can offer books for exchange and request books from other users. The system includes location-based filtering (focused on Buenos Aires areas) and manages exchange requests between users.

## Development Commands

**Note**: This project uses `uv` for dependency management. All Python commands should be run with `uv run` prefix (e.g., `uv run python manage.py`).

The most important commands are specified in a Makefile. Use the makefile as documentation but don't NEVER run make commands.

## Architecture

See Models (books/models.py)

## Django Configuration

- **Database**: SQLite (db.sqlite3)
- **Python Version**: >= 3.14
- **Django Version**: >= 4.2.26
- **Settings Module**: giralibros.settings
- **Installed Apps**: Standard Django apps + 'books'
- **Admin Interface**: Enabled at /admin/

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
3. Assume files are read top-bottom and preserve readability in this context: helper functions should be prefixed with _ and go to:
  a. the bottom of the file if they are to be used by multiple unrelated functions
  b. right next to the functions/methods that called them if it's not a general purpose helper but a snippet of code extraction.
4. Modules should be deep---this applies to python module files, classes and functions/methods. don't break functions into smaller ones unless there's a good reason for it (e.g. immediate need to reuse)

## Frontend & Styling

- **CSS Framework**: Bulma (https://bulma.io/documentation/)
- **Icons**: FontAwesome
- **JavaScript**: Vanilla JS (no frameworks)

**Important**: Leverage Bulma as much as possible for layout and styling. Do not create custom CSS components or inline styles for things already handled by Bulma. Refer to the Bulma documentation when building UI components to use the appropriate classes and modifiers.
