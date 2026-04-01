---
description: "Use when writing or reviewing any Python file under api/. FastAPI backend conventions for the txr_automation webapp."
applyTo: "api/**"
---

# Backend Conventions (api/)

## Architecture
- Route handlers in `api/routers/` are thin — delegate to `api/services/`
- Business logic in `api/services/` — no HTTP-specific code here
- Long-running operations dispatched as Celery tasks in `api/tasks/`
- Existing `src/` modules called from services/tasks — never from routers directly

## FastAPI Patterns
- All route handlers `async def`
- Pydantic v2 schemas for all request/response bodies (no raw dicts)
- `model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)` on all schemas
- `Depends()` for DB sessions and shared dependencies
- All routes prefixed `/api/`; register routers in `api/main.py`

## Celery Tasks
- Capture stdout/stderr: `contextlib.redirect_stdout` + `io.StringIO`
- Publish logs: `redis_client.publish(f"job:{job_id}:logs", json.dumps({"type": "log", "data": line}))`
- Status updates: PENDING → RUNNING → SUCCESS | FAILED
- Call scripts: `module.main(argv)` — see `src/gui/workers/script_runner.py`

## Imports from src/
```python
# Correct — import module, call main() with argv
from src.accuracy_testing.scripts import buyer_id_validation
buyer_id_validation.main(["--config", str(config_path)])

# Correct — call managers directly for quick lookups
from src.firds.cache_manager import FirdsCacheManager
from src.gleif.lookup import GleifLookup
```

## Inherited Conventions (all existing rules apply)
- Python 3.10+ type hints required on all functions
- Google-style docstrings on all public functions and classes
- British English in all prose
- `create_logger(__name__)` from `src.core.logging`
- DO NOT modify any file under `src/`
