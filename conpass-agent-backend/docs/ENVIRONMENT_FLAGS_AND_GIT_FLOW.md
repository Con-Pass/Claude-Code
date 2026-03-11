# Environment Flags and Git Flow

This document describes how environment-based feature gating works in ConPass Agent and the git flow practices that make the most of it.

---

## 1. Environment Flags Overview

### Purpose

Environment flags let you **turn behavior on or off by environment** (development, staging, production). The same codebase is deployed to all three; behavior differs based on the `ENVIRONMENT` setting at runtime.

Benefits:

- **Single promotion path**: Merge `development` → `staging` → `main` without cherry-picking. No need to merge the same feature into three branches separately.
- **Fewer conflicts**: One linear flow instead of parallel merges into dev, stage, and main.
- **Safe rollout**: Experimental or dev-only behavior stays off in staging and production because it is gated by environment checks.

### How It Works

- **Config**: `app/core/config.py` defines `ENVIRONMENT` with allowed values: `"development"`, `"staging"`, `"production"`, `"test"`.
- **Runtime**: Each deployment sets `ENVIRONMENT` via environment variable (e.g. in Cloud Run, `.env`, or CI/CD). Default is `"development"`.
- **Gating**: Code uses helpers from `app/core/environment_flags.py` to branch behavior.

### Available Helpers

| Helper | Returns `True` when |
|--------|---------------------|
| `is_development()` | `ENVIRONMENT` is `"development"` or `"test"` |
| `is_staging()` | `ENVIRONMENT` is `"staging"` |
| `is_production()` | `ENVIRONMENT` is `"production"` |

**Important**: These are **functions**. Always call them: `is_development()`, not `is_development`. Using the function object without `()` is always truthy and will enable the branch in every environment.

---

## 2. Using Environment Flags in Code

### Where They Live

- **Definition**: `app/core/environment_flags.py`
- **Config**: `settings.ENVIRONMENT` in `app/core/config.py`

### Usage Examples

```python
from app.core.environment_flags import is_development, is_staging, is_production

# Dev-only behavior (e.g. experimental prompts, extra logging)
if is_development():
    use_experimental_prompt()
else:
    use_stable_prompt()

# Enable in dev and staging, disable in production
if not is_production():
    emit_verbose_debug_events()

# Staging-specific behavior (e.g. beta feature)
if is_staging():
    enable_beta_search()
```

### Current Usage in the Codebase

Environment flags are used to gate:

- **Chat / engine**: Experimental system prompts (e.g. JP v5), different run handlers, date injection in dev.
- **Events**: Extra serialization of `raw_output` in development.
- **Vercel response**: Different truncation of candidate messages in dev.
- **Schemas**: Stricter validation (e.g. requiring at least one message) in development.

When adding new dev-only or staging-only behavior, use the same pattern and document it in code comments or this doc.

---

## 3. Environment vs Feature Flags

| Aspect | This project (environment flags) | Full feature-flag systems |
|--------|----------------------------------|----------------------------|
| **Control** | Single “mode” per deploy (dev/stage/prod) | Per-feature toggles, often in config/API |
| **Change** | Redeploy or change `ENVIRONMENT` | Toggle without app deploy (or config-only deploy) |
| **Granularity** | One environment per deployment | Many independent features, sometimes per user or % rollout |

Environment flags are the right tool for “don’t run dev-only stuff in stage/prod” and for a simple dev → stage → main flow. If you later need “turn on new search in prod without deploy” or percentage rollouts, consider adding a dedicated feature-flag system (e.g. LaunchDarkly, Unleash, or a small config/DB layer).

---

## 4. Git Flow Practices

These practices are designed to work with environment flags and the single promotion path (dev → stage → main).

### Branch Model

- **`development`** – Integration branch for daily work. Deployed to dev environment. May contain incomplete or experimental features gated by `is_development()`.
- **`staging`** – Pre-production. Deployed to staging. Should be stable; only features ready for staging (or gated by flags) should be active.
- **`main`** – Production. Deployed to production. Must be stable; no experimental behavior unless behind `is_production()` checks.

### Promotion Path

```
development  →  staging  →  main
     (dev)        (stage)     (prod)
```

- **development → staging**: Merge when the dev branch is in a good state for staging testing. Features not ready for staging should be **off** in staging via environment (e.g. behind `is_development()`).
- **staging → main**: Merge when staging has been validated and you are ready for production release.

### Feature Workflow

1. **Create a feature branch from `development`**  
   - Example: `feature/contract-search-v2`, `fix/upload-validation`.

2. **Develop and test locally**  
   - Use `ENVIRONMENT=development` (or default). Use `is_development()` for experimental or noisy behavior.

3. **Merge into `development`**  
   - Open a PR into `development`. After review, merge.  
   - If the feature is **not** ready for staging/production, gate it with `is_development()` (or `is_staging()` if it should appear in staging only).

4. **Promote via merges**  
   - When ready: merge `development` → `staging`, then after validation merge `staging` → `main`.  
   - No need to open separate PRs from the feature branch into staging or main; the promotion path carries the changes.

### Rules of Thumb

- **One direction**: Merge only **development → staging → main**. Avoid merging main or staging back into development except for rare hotfixes (see below).
- **Feature branches merge into `development`**: Keep `development` as the single integration target for feature work.
- **Gate, don’t remove**: If something must not run in staging/production yet, gate it with `is_development()` (or `is_staging()`) instead of maintaining separate branches for each environment.
- **Hotfixes**: For urgent production fixes, branch from `main`, fix, merge back to `main`, then merge `main` into `staging` and `development` so all branches get the fix.

### Avoiding Merge Conflicts

- Merge **development → staging** and **staging → main** regularly (e.g. after each release or at a set cadence). Long-lived divergence increases conflicts.
- Keep feature branches short-lived and merge into `development` often.
- Resolve conflicts in the promotion branch (e.g. in `staging` when merging from `development`) so that `main` receives already-resolved code.

### Summary Diagram

```
feature/xyz  ──PR──►  development  ──merge──►  staging  ──merge──►  main
                           │                        │                  │
                      (dev deploy)            (stage deploy)      (prod deploy)
                      ENVIRONMENT=development  ENVIRONMENT=staging  ENVIRONMENT=production
```

---

## 5. Checklist for New Dev-Only or Staging-Only Behavior

- [ ] Use `is_development()` or `is_staging()` / `is_production()` from `app.core.environment_flags`.
- [ ] Call the function: `is_development()`, not `is_development`.
- [ ] Add a short comment in code explaining why the behavior is gated.
- [ ] Ensure the default or fallback path is safe for production (no secrets, no verbose PII, no unstable behavior).
- [ ] If the behavior is large or risky, consider documenting it in this file under “Current usage in the codebase”.

---

## 6. Configuration per Environment

| Environment | Branch | Typical use |
|-------------|--------|-------------|
| Development | `development` | Local and dev deployment; experimental features and verbose logging. |
| Staging | `staging` | Pre-production testing; same code as prod, with staging data and `ENVIRONMENT=staging`. |
| Production | `main` | Live traffic; `ENVIRONMENT=production`; only production-ready behavior. |

Set `ENVIRONMENT` in each deployment (e.g. Cloud Run env vars, `.env` for local) so the correct branch of environment-gated code runs.
