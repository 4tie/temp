# Loop Narration + Delta Reporting + Markdown Audit — Implementation Audit

## Scope
Implemented the requested loop behavior for chat-visible narration with backend loop orchestration, result/file/test snippets, and markdown audit reporting.

## Workflow now implemented
1. User enables loop with `Start Loop` in chat context bar.
2. User clicks `apply` on a Python code block.
3. Frontend starts backend loop with `POST /ai/loop/start`.
4. Frontend subscribes to `GET /ai/loop/{loop_id}/stream` and narrates each step in chat.
5. Backend stages:
   - `loop_started`
   - `apply_done`
   - `ai_validate_done` (frontend prompts rerun confirmation)
   - `rerun_started`
   - `rerun_done`
   - `result_diff`
   - `file_diff`
   - `tests_done`
   - `cycle_done`
6. Frontend renders:
   - planned steps
   - backtest rerun metadata
   - full result delta table snippet
   - `.py` / `.json` change status and diff snippets
   - test table and output snippets
   - final report path
7. Stop path:
   - `POST /ai/loop/{loop_id}/stop`
   - chat receives `loop_stopped` summary.

## Files changed
- `app/routers/ai_chat.py`
- `app/schemas/ai_chat.py`
- `app/test_ai_chat_router.py`
- `static/js/pages/ai-diagnosis.js`
- `app/core/config.py` (already included in prior step for reports directory)

## Key backend additions
- New loop endpoints:
  - `POST /ai/loop/start`
  - `POST /ai/loop/{loop_id}/confirm-rerun`
  - `POST /ai/loop/{loop_id}/stop`
  - `GET /ai/loop/{loop_id}/stream`
  - `GET /ai/loop/{loop_id}/report`
- Reused apply logic via shared `_apply_code_impl(...)`.
- Added per-stage event emission with `md_report_path` attached.
- Added result delta rows generator and file diff summary transport.
- Added targeted validation test runner stage.
- Added incremental markdown writer under `user_data/ai_loop_reports/<loop_id>.md`.

## Key frontend additions
- Replaced old hidden client-side loop execution with backend SSE-driven loop narration.
- Added loop event rendering in chat for all stages.
- Added rerun confirmation handoff via `/confirm-rerun`.
- Added remote stop behavior via `/stop`.
- Keeps non-loop `apply` behavior unchanged.

## Verification executed in this environment
### 1) Python compile checks
Command:
```bash
python -m py_compile app/routers/ai_chat.py app/schemas/ai_chat.py app/test_ai_chat_router.py
```
Result: **PASS**

### 2) JS syntax check
Command:
```bash
node --check static/js/pages/ai-diagnosis.js
```
Result: **PASS**

### 3) Unit test execution
Command:
```bash
python -m unittest -q app.test_ai_chat_router
```
Result: **FAILED in this environment**
Reason:
```text
ModuleNotFoundError: No module named 'fastapi'
```
This is an environment dependency issue, not a syntax issue in modified files.

## Added/updated tests
- `app/test_ai_chat_router.py`
  - loop start creates session/report path
  - loop confirm updates session
  - loop report returns markdown preview

## Notes
- Loop remains semi-auto: rerun requires explicit user confirmation each cycle.
- Markdown audit path is deterministic per loop ID: `user_data/ai_loop_reports/<loop_id>.md`.
- Frontend now narrates steps directly in chat with snippets for results, file changes, and tests.
