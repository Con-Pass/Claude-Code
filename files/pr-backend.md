# [PoC] Law & Playbook Models, APIs, and Migrations

## Summary

This branch (`poc/rag-pipeline-tuning`) adds the Django models, CRUD APIs, and migrations required by the conpass-agent-backend PoC for law management and playbook/template features. These provide the data management layer that the AI agent's law search tool and template comparison tool depend on.

**No RAG implementation is included in this repository.** All RAG/AI logic resides in conpass-agent-backend. This PR only adds models and REST APIs.

## Changes

### ④ Law Management
- **Models**: `LawDocument` (status: PENDING/INDEXED/FAILED, article_count, applicable_contract_types, search_keywords) and `LawFile`
- **API** (`views/setting/law_view.py`): Law upload, list, delete, and re-index endpoints under `setting/law/*`
- **Migrations**: 0080 (LawDocument), 0081 (LawFile), 0082 (alter file_path), 0083 (add applicable_contract_types and search_keywords)

### ① Playbook
- **Models** (`models/playbook.py`): 8 models — PlaybookTemplate, TenantPlaybook, ClausePolicy, TenantRuleSet, TenantRule, RuleEvaluationLog, ResponseTemplate, TemplateVariable
- **Service** (`services/playbook/playbook_service.py`): Playbook business logic
- **API** (`views/playbook/views.py`): Playbook CRUD endpoints with serializers

### Cross-cutting
- **Model registration** (`models/__init__.py`): Added imports for LawDocument, LawFile, and all 8 Playbook models. Removed: GmoSign, GmoSignSigner (MS2 scope)
- **URL routing** (`urls.py`): Added `setting/law/*` and `playbook/*` paths. Removed: `gmo-sign/*`, `compliance/rescore/`, `contract/rescan/`, `local-file/*` (out of scope)
- **Settings** (`settings/__init__.py`): Added `AGENT_INTERNAL_URL` for communication with conpass-agent-backend
- **Dependencies** (`Pipfile`): Added `pdfminer-six` for law PDF text extraction. Removed: `openai` (only used in local mock)

## Discussion Points

1. **Law management UI placement**: The law CRUD API is currently under `setting/law/*` (admin-side). Should we also add a read-only interface on the user-facing side, or keep it admin-only with the AI agent serving as the user-facing access point for law-related queries?

2. **Playbook UI placement**: The full CRUD API is implemented. Recommended split for discussion:
   - **Admin side**: Register, edit, delete templates; configure tenant-specific rules and policies
   - **User side**: Browse available templates; compare templates against own contracts; view clause policies
   - This split would require adding user-facing read-only endpoints in a follow-up

3. **Migration ordering**: Migrations 0080–0083 are sequential and depend on the current `prod` branch state. If other migrations have been added to `prod` since this branch was created, migration conflicts may need to be resolved before merge.

## Not Included

| Item | Reason |
|------|--------|
| GMO Sign models/APIs | MS2 scope — imports and URLs removed from this branch |
| Compliance rescore endpoint | Out of PoC scope |
| Contract rescan endpoint | Out of PoC scope |
| Local file endpoints | Out of PoC scope |
| Vue frontend changes | No frontend repository available for PR |

## Relationship to conpass-agent-backend PR

This PR is paired with a corresponding PR on `conpass-agent-backend` (same branch name: `poc/rag-pipeline-tuning`). The agent-backend PR contains the RAG pipeline, AI tools, and evaluation infrastructure that consume the models and APIs added here.

Both PRs should be reviewed and merged together.

## How to Test

```bash
# 1. Run migrations
python manage.py migrate

# 2. Verify law API
curl -X GET http://localhost:8000/api/setting/law/
curl -X POST http://localhost:8000/api/setting/law/upload/ -F "file=@sample_law.pdf"

# 3. Verify playbook API
curl -X GET http://localhost:8000/api/playbook/
```
