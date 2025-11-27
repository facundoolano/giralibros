# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Cambiolibros is a Django-based book exchange platform where users can offer books for exchange and request books from other users. The system includes location-based filtering (focused on Buenos Aires areas) and manages exchange requests between users.

## Development Commands

### Environment Setup
```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
uv sync

# Install dev dependencies
uv sync --group dev
```

### Database Management
```bash
# Run migrations
python manage.py migrate

# Create migrations after model changes
python manage.py makemigrations

# Create superuser for admin access
python manage.py createsuperuser
```

### Running the Application
```bash
# Start development server
python manage.py runserver

# Admin interface available at http://localhost:8000/admin/
```

### Testing and Type Checking
```bash
# Run tests
python manage.py test

# Type checking with mypy (django-stubs configured)
mypy .
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
cambiolibros/          # Django project configuration
  settings.py          # Django settings (SQLite database, installed apps)
  urls.py             # URL routing (currently only admin)

books/                 # Main application
  models.py           # All data models
  admin.py            # Admin interface configuration
  views.py            # View logic (currently empty)
  migrations/         # Database migrations
```

## Django Configuration

- **Database**: SQLite (db.sqlite3)
- **Python Version**: >= 3.14
- **Django Version**: >= 4.2.26
- **Settings Module**: cambiolibros.settings
- **Installed Apps**: Standard Django apps + 'books'
- **Admin Interface**: Enabled at /admin/

## Type Checking

The project uses django-stubs for type checking. Configuration in pyproject.toml:
```toml
[mypy.plugins.django-stubs]
django_settings_module = "cambiolibros.settings"
```
