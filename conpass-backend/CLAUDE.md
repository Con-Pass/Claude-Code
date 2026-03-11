# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ConPass (conpass-backend) is an enterprise electronic contract management system (電子契約システム) built for Nihon Purple. It is a Django 3.2 REST API backend using Django REST Framework, with MySQL, Celery (Redis broker), and integrations with GCP (Vision, AutoML, Cloud Storage), Azure AI, AdobeSign, and SendGrid.

## Common Commands

### Development Environment
```bash
docker-compose up              # Start all services (app, worker, db, redis, maildev, keycloak, nginx)
```

### Running Tests
```bash
# Full test suite with coverage
pipenv run pytest tests/ --showlocals --cov-report=html:htmlcov --cov=app

# Single test file
pipenv run pytest tests/conpass/test_example.py

# Single test function
pipenv run pytest tests/conpass/test_example.py::test_function_name -v

# Via tox (includes install)
tox -e py38
```

Tests use `DJANGO_SETTINGS_MODULE=config.settings.testing` and `.env.testing` automatically.

### Linting & Formatting
```bash
pipenv run lint                # flake8 linting (max-line-length=160, ignores F401/F403)
pipenv run fix                 # autopep8 auto-format
tox -e flake8                  # Lint via tox
```

### Django Management
```bash
# Run from app/ directory
pipenv run python manage.py makemigrations
pipenv run python manage.py migrate
pipenv run python manage.py createsuperuser
```

## Architecture

### Request Flow
```
Nginx (:8800) → uWSGI (:8000) → Django Middleware → JWT Auth → DRF Views → Services → ORM → MySQL
```

### Key Directory Structure (under `app/`)
- **`config/`** — Django settings (split by environment: `local`, `testing`, `develop`, `production`), URL routing, Celery config
- **`conpass/`** — Main business application
  - `models/` — Django ORM models (custom User model extending AbstractUser)
  - `views/` — DRF API views organized by domain (contract, workflow, user, account, etc.)
  - `services/` — Business logic layer (contract processing, file uploads, GCP/Azure AI, metadata, etc.)
  - `mailer/` — Email sending via SendGrid with HTML templates in `templates/`
  - `management/` — Custom Django management commands
  - `migrations/` — Database migrations
  - `tasks.py` — Celery async tasks (vision scanning, predictions, batch jobs)
- **`common/`** — Shared utilities
  - `auth/` — JWT authentication with dual cookie support (`auth-token` for users, `auth-token-sys` for admins)
  - `middleware/` — Custom middleware (request user logging)
  - `utils/` — Validators, helpers
- **`internal_api/`** — Celery job scheduling endpoints (enabled when `IS_INTERNAL_APP_SERVER=true`)
- **`saml_extension/`** — SAML 2.0 SSO integration with Keycloak

### URL Routing
- `/api/` → `conpass.urls` (main API)
- `/admin/` → Django admin
- `/saml/` → SAML 1.0 (django-saml)
- `/saml2/` → SAML 2.0 (custom extension)
- `/internal-api/` and `/private/` → Worker task endpoints (conditional)

### User Types
- `ACCOUNT (1)` — Customer/contract users
- `CLIENT (2)` — Trading partners
- `ADMIN (3)` — System administrators (Purple staff)

### Key Patterns
- **Service layer**: Business logic lives in `conpass/services/`, not in views
- **Multi-tenant**: Account-based isolation with role-based permissions
- **Flexible metadata**: Generic MetaKey/MetaData system for dynamic contract attributes
- **Workflow engine**: Approval workflows with steps and task assignments
- **Dual JWT cookies**: Separate auth cookies for user-facing and admin interfaces
- **CamelCase API responses**: Uses `djangorestframework-camel-case` for JSON key transformation

### Test Fixtures (in `app/conftest.py`)
- `login_user` / `api_client` — Standard authenticated user (Type: ACCOUNT)
- `login_admin` / `sys_client` — Admin authenticated user (Type: ADMIN)
- Uses `pytest-factoryboy` factories in `conpass/tests/factories/`
- `freezegun` available for datetime mocking

## Ports (Docker)
| Port | Service |
|------|---------|
| 8800 | Nginx (frontend proxy) |
| 8802 | MySQL |
| 8803 | Redis |
| 8804 | Maildev (browser UI) |
| 8806 | Celery worker endpoint |
