# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ConPass is a three-service enterprise contract management platform (電子契約システム):

| Service | Stack | Purpose |
|---------|-------|----------|
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
  ├── Qdrant cloud  — contract vector embeddings (collection: conpass_bge_m3)
  ├── GCP Firestore — feature flags, chat history
  └── conpass-backend API — internal data access
```

## Development Commands

### Full Stack (conpass-backend/)

```bash
cd conpass-backend
docker-compose up
docker-compose up -d --force-recreate app worker worker2  # .env変更後に必要
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

### Agent Backend (conpass-agent-backend/)

```bash
# Docker (本番スタイル)
docker build -t conpass-agent .
docker rm -f conpass-agent && docker run -d --name conpass-agent \
  --env-file .env \
  -p 8000:8080 \
  --network conpass-backend_default \
  conpass-agent
```

## Architecture Notes

### conpass-agent-backend 重要情報

- **LLM**: OpenAI gpt-4o-mini (LlamaIndex経由)
- **Embedding**: BGE-M3 (BAAI/bge-m3) — 1024次元 Dense + SPLADE Sparse
- **Vector store**: Qdrant Cloud — コレクション名 `conpass_bge_m3`
- **Payload indexes**: `contract_id` (INTEGER), `directory_id` (INTEGER), `private` (BOOL)
- **Feature flags**: Firestore-backed (`MULTI_AGENT_ENABLED=false` がデフォルト)
- **GoogleGenAI は未使用** → 全 extractor で `Settings.llm` (OpenAI) を使用

## Workflow Orchestration

### 1. Plan Node Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately

### 2. Subagent Strategy
- Use subagents liberally to keep main context window clean
- One task per subagent for focused execution

### 3. Verification Before Done
- Never mark a task complete without proving it works
- Run tests, check logs, demonstrate correctness

## Core Principles

- **Simplicity First**: Make every change as simple as possible.
- **No Laziness**: Find root causes. No temporary fixes.
- **Minimal Impact**: Changes should only touch what's necessary.
