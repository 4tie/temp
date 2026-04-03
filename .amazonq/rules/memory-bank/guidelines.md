# Development Guidelines — 4tie

## Code Quality Standards

### Module Structure
- All `__init__.py` files are intentionally empty — packages use explicit imports only
- No wildcard imports (`from module import *`) anywhere in the codebase
- Each module has a single clear responsibility; no cross-cutting logic in `__init__.py`

### Import Ordering Convention
```python
# 1. stdlib
import json, os, uuid, threading
from pathlib import Path
from typing import Any, Optional

# 2. third-party
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# 3. internal (absolute paths from app root)
from app.core.config import BACKTEST_RESULTS_DIR
from app.services.runner import start_backtest
```

### Naming Conventions
- Module-private helpers prefixed with `_` (e.g., `_read_config_json`, `_checked_id`, `_ensure_valid_strategy_json`)
- Constants in `UPPER_SNAKE_CASE` at module level (e.g., `BACKTEST_RESULTS_DIR`, `VALID_TIMEFRAMES`)
- Async functions named without `async_` prefix — async is implied by context
- Worker threads named `_*_worker` (e.g., `_backtest_worker`, `_download_worker`, `_hyperopt_worker`)
- Run IDs use datetime prefix + UUID hex suffix: `"%Y%m%d_%H%M%S" + "_" + uuid4().hex[:8]`

---

## Structural Conventions

### Router Pattern
Every router follows this structure:
```python
router = APIRouter(tags=["domain_name"])  # no prefix on backtest; prefix="/ai" on ai_chat

# Private helpers at top
def _helper() -> ...: ...

# Endpoints below helpers
@router.get("/path")
async def endpoint_name(req: SchemaModel):
    ...
    return {...}
```
- Routers never contain business logic — they delegate to `app/services/`
- Input validation via Pydantic schemas, not manual checks in router functions
- ID validation done via a shared `_checked_id()` helper before any file I/O

### Service Layer Pattern
- Services are plain functions (not classes), imported directly
- Long-running operations (backtest, download, hyperopt) use `threading.Thread(daemon=True)`
- Subprocess pattern is consistent across all workers:
```python
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
set_process(job_id, proc)
for line in proc.stdout:
    append_log(job_id, line.rstrip())
proc.wait()
if proc.returncode == 0:
    set_status(job_id, "completed")
else:
    set_status(job_id, "failed")
```

### Schema Pattern (Pydantic v2)
```python
class SomeRequest(BaseModel):
    required_field: str
    optional_field: Optional[str] = None
    list_field: list[str]
    dict_field: dict[str, Any] = Field(default_factory=dict)
    numeric_with_default: int = 100
```
- Use `model_dump()` (not `.dict()`) and `model_dump(exclude_none=True)` for partial updates
- `Field(default_factory=...)` for all mutable defaults (lists, dicts)

### Config / Path Pattern
All paths are `pathlib.Path` objects resolved from `BASE_DIR`:
```python
BASE_DIR = Path(os.environ.get("USER_DATA_DIR", Path(__file__).resolve().parents[2] / "user_data"))
SOME_DIR = BASE_DIR / "subdir"
SOME_DIR.mkdir(parents=True, exist_ok=True)  # created at import time
```
- Never use `os.path.join` — always use `/` operator on `Path` objects
- Directories are created at startup in `config.py`, not lazily

---

## Error Handling Patterns

### Router Error Handling
```python
# 404 pattern
item = load_something(id)
if not item:
    raise HTTPException(status_code=404, detail="Item not found")

# 400 validation pattern
if not _SAFE_ID_RE.match(value):
    raise HTTPException(status_code=400, detail="Invalid ID")
```

### Service Error Handling
- Workers catch `FileNotFoundError` separately (freqtrade not installed) vs generic `Exception`
- All exceptions in workers are logged via `append_log(run_id, f"ERROR: {str(e)}")`
- Meta is always saved on completion/failure — even in the `except` block
- `finally: remove_process(run_id)` ensures cleanup regardless of outcome

### File I/O Error Handling
```python
# Safe read — never raises
def read_json(path: Path, default: Any = None) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

# Atomic write for critical files
tmp_fd, tmp_path = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
try:
    with os.fdopen(tmp_fd, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, target)
except Exception:
    os.unlink(tmp_path)
    raise
```

---

## AI Pipeline Patterns

### Pipeline Dataclasses
Use `@dataclass` with `field(default_factory=list)` for mutable fields:
```python
@dataclass
class PipelineResult:
    final_text: str
    pipeline_type: str
    steps: list[PipelineStep] = field(default_factory=list)
    run_id: str = ""

    def to_dict(self) -> dict:
        # Always exclude output_full from serialized logs
        ...
```

### Streaming Pattern (SSE)
All streaming functions are `AsyncGenerator[dict, None]`:
```python
async def stream_something(...) -> AsyncGenerator[dict, None]:
    yield {"status": "working", "done": False}   # progress events
    yield {"delta": chunk_text, "done": False}    # content chunks
    yield {"done": True, "fullText": full, "pipeline": info}  # terminal event
```
- SSE lines formatted as: `f"data: {json.dumps(data)}\n\n"`
- Error events: `yield {"error": "message", "done": True}` — always include `done: True`
- Status events use string labels: `"classified"`, `"reasoning"`, `"composing"`, `"judging"`, `"generating_code"`, `"validating_code"`, `"explaining"`

### Role-Based Model Selection
Models are selected by role string, with optional overrides:
```python
model_id, reason = get_model_for_role("reasoner", models, role_overrides)
# role_overrides: dict[str, str] | None — maps role name → model ID
```
Roles used: `"reasoner"`, `"analyst_a"`, `"analyst_b"`, `"composer"`, `"explainer"`, `"code_gen"`, `"judge"`, `"tool_caller"`, `"structured_output"`, `"classifier"`

### Fallback Pattern
```python
try:
    result = await chat_complete(messages, model=model_id)
except Exception as e:
    logger.warning("Model %s failed: %s — trying fallback", model_id, e)
    result = await chat_complete(messages, model=LAST_RESORT_MODEL)
    model_id = LAST_RESORT_MODEL
```

### Parallel Execution
Use `asyncio.gather` for concurrent model calls:
```python
analyst_a_task = _call_model("analyst_a", msgs, models, role_overrides)
analyst_b_task = _call_model("analyst_b", msgs, models, role_overrides)
analyst_a_step, analyst_b_step = await asyncio.gather(analyst_a_task, analyst_b_task)
```

---

## Logging Conventions
- Use `logging.getLogger(__name__)` at module level — never `print()` in production code
- Log levels: `logger.info` for pipeline decisions, `logger.warning` for recoverable errors, `logger.error` for failures
- Format: `logger.warning("Context %s: %s", identifier, error)` — use `%s` formatting, not f-strings

---

## Regex & Validation Patterns
- Compile regex at module level as constants: `_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")`
- Strategy parameter extraction uses `re.compile` patterns with named groups via positional groups
- JSON extraction from LLM output: find `{` and `}` by index, then `json.loads` the slice

---

## Frontend Conventions (Vanilla JS)
- No framework — DOM manipulation via `document.querySelector` / `document.getElementById`
- API calls via custom wrapper in `static/js/core/api.js`
- SSE handled manually: parse `data: {...}` lines, check `done` flag
- Page controllers are self-contained modules, one per page
- Hash-based routing: `window.location.hash` → load page fragment

---

## FreqTrade-Specific Conventions
- Strategy JSON sidecars (`StrategyName.json`) contain only scalar values (str/int/float/bool/null)
- Non-scalar values in strategy JSON are rejected and reset to `{}` before running
- Run IDs for backtests: `YYYYMMDD_HHMMSS_<8hex>` (no prefix)
- Run IDs for downloads: `dl_YYYYMMDD_HHMMSS_<8hex>`
- Run IDs for hyperopt: `ho_YYYYMMDD_HHMMSS_<8hex>`
- Valid timeframes defined in `config.py` as `VALID_TIMEFRAMES` list — always validate against this
- Exchange config in `config.json` may be a string or `{"name": "..."}` dict — handle both forms
