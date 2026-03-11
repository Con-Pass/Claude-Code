# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ConPass is a three-service enterprise contract management platform (電子契約システム):

| Service | Stack | Purpose |
|---------|-------|---------|
| `conpass-backend/` | Django 3.2 + DRF (Python 3.8) | Core business API |
| `conpass-frontend/` | Vue 3 + TypeScript + Vite | Web UI |
| `conpass-agent-backend/` | FastAPI (Python 3.12) | AI agent & RAG backend |

## Service Interactions

```
Browser → Nginx (:8800)
  ├── /api/*    → conpass-backend uWSGI (:8000)
  ├── /admin/*  → conpass-backend uWSGI (:8000)
  └── /*        → Vite dev server (:8801) — Vue SPA

Browser → conpass-agent (:8000 host / :8080 container)
  ├── Qdrant cloud  — contract vector embeddings (collection: conpass-contracts)
  ├── GCP Firestore — feature flags, chat history
  └── conpass-backend API — internal data access
```

The frontend `src/api/client.ts` uses `baseURL: '/api'` with `withCredentials: true`. All API calls go through Nginx to the backend.

## Development Commands

### Full Stack (conpass-backend/)

```bash
cd conpass-backend
docker-compose up                                          # Start everything
docker-compose up -d --force-recreate app worker worker2  # Required after .env changes
```

**Port map:**

| Port | Service |
|------|---------|
| 8800 | Nginx (main entry point) |
| 8801 | Vite dev server |
| 8802 | MySQL |
| 8803 | Redis |
| 8804 | Maildev UI |
| 8806 | Celery worker |
| 18080 | Keycloak (SSO) |

> `docker restart` does **not** reload `env_file`. Use `--force-recreate` after `.env` changes.

### Backend (conpass-backend/)

Commands run inside Docker — `manage.py` is at `/app/app/manage.py` in the container:

```bash
# Tests
docker-compose exec app bash -c "cd /app/app && pipenv run pytest tests/ --showlocals --cov=app"

# Single test
docker-compose exec app bash -c "cd /app/app && pipenv run pytest tests/conpass/test_foo.py::test_bar -v"

# Lint / format
docker-compose exec app pipenv run lint   # flake8
docker-compose exec app pipenv run fix    # autopep8

# Django management (from /app/app inside container)
docker-compose exec app bash -c "cd /app/app && python manage.py migrate"
docker-compose exec app bash -c "cd /app/app && python manage.py shell"
```

uWSGI runs with `--py-autoreload 1`, so Python file edits are picked up automatically without restart.

See `conpass-backend/CLAUDE.md` for detailed backend architecture and patterns.

### Frontend (conpass-frontend/)

```bash
cd conpass-frontend
npm install
npm run dev      # Vite dev server on :8801
npm run build    # vue-tsc + vite build (production)
npm run preview  # Preview production build
```

### Agent Backend (conpass-agent-backend/)

```bash
cd conpass-agent-backend
uv sync                                                  # Install dependencies
uv run uvicorn app.main:app --reload --port 8080         # Dev server
uv run pytest                                            # Tests

# Docker (production-style)
docker build -t conpass-agent .
docker run -p 8000:8080 conpass-agent
```

## Architecture Notes

### conpass-backend Key Patterns

- **Service layer**: All business logic in `conpass/services/`, never in views
- **Multi-tenant**: Account-based isolation; user types: ACCOUNT(1), CLIENT(2), ADMIN(3)
- **Auth**: Dual JWT cookies — `auth-token` (users) / `auth-token-sys` (admins)
- **Async**: Celery + Redis for OCR, predictions, batch jobs (`conpass/tasks.py`)
- **API responses**: CamelCase via `djangorestframework-camel-case`
- **Local OCR fallback**: `services/gcp/vision_service_local_patch.py` intercepts GCP Vision/GvPredict calls and uses pdfminer + `gpt-4o-mini` (vision) when GCP credentials are unavailable. Model must be accessible to the configured `OPENAI_API_KEY`.
- **Testing**: `login_user`/`api_client` (ACCOUNT type) and `login_admin`/`sys_client` (ADMIN type) fixtures in `app/conftest.py`

### conpass-agent-backend Key Patterns

- **LLM**: LlamaIndex with OpenAI (primary) and Google GenAI
- **Vector store**: Qdrant cloud with `all-MiniLM-L6-v2` embeddings (FastEmbed)
- **Feature flags**: Firestore-backed, loaded at runtime via `services/chatbot/feature_flags.py`
- **Observability**: Langfuse + OpenInference tracing
- **Config**: Pydantic-settings in `app/core/config.py`
- **Auth middleware**: JWT verification in `app/core/middleware.py`

### Frontend Key Patterns

- **API client**: `src/api/client.ts` — axios instance, `baseURL: '/api'`, cookies enabled
- **State**: Pinia stores in `src/stores/`
- **Routing**: Vue Router in `src/router/`

## Workflow Orchestration

### 1. Plan Node Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately – don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy
- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop
- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes – don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests – then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how

## Task Management

1. **Plan First**: Write plan to `tasks/todo.md` with checkable items
2. **Verify Plan**: Check in before starting implementation
3. **Track Progress**: Mark items complete as you go
4. **Explain Changes**: High-level summary at each step
5. **Document Results**: Add review section to `tasks/todo.md`
6. **Capture Lessons**: Update `tasks/lessons.md` after corrections

## Core Principles

- **Simplicity First**: Make every change as simple as possible. Impact minimal code.
- **No Laziness**: Find root causes. No temporary fixes. Senior developer standards.
- **Minimal Impact**: Changes should only touch what's necessary. Avoid introducing bugs.
