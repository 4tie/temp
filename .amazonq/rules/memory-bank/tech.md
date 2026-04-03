# Technology Stack — 4tie

## Programming Languages
- **Python 3.11+** — Backend (FastAPI app, AI pipelines, services)
- **JavaScript (ES6+, vanilla)** — Frontend SPA (no framework)
- **HTML5 / Jinja2** — Templating
- **CSS3** — Styling (modular, no preprocessor)

## Backend Framework & Dependencies

### Core (requirements.txt)
```
fastapi>=0.100.0
uvicorn>=0.20.0
numpy>=1.24.0
pandas>=2.0.0
```

### FastAPI Features Used
- `APIRouter` with tags for domain grouping
- `Pydantic BaseModel` for all request/response schemas
- `StreamingResponse` with `text/event-stream` for SSE
- `Jinja2Templates` for server-side HTML rendering
- `StaticFiles` mount for `/static`
- `CORSMiddleware` (allow all origins — development config)

### External Integrations
- **FreqTrade** — Invoked as a subprocess via `subprocess.Popen`; results read from filesystem
- **OpenRouter API** — Cloud AI provider (requires `OPENROUTER_API_KEY`)
- **Ollama** — Local AI provider (HTTP to `http://localhost:11434`)

## Build System & Dev Server

### Running the App
```bash
python run.py
```
- Starts uvicorn on port `5000` (default) or `$BACKTEST_API_PORT`
- Hot-reload watches: `app/`, `templates/`, `static/`
- Host: `0.0.0.0` (accessible externally)

### No Build Step
- Frontend is vanilla JS — no bundler, no transpilation
- CSS is plain CSS — no Sass/Less
- Templates are Jinja2 rendered server-side on first load, then SPA takes over

## Environment Variables
| Variable | Default | Purpose |
|---|---|---|
| `BACKTEST_API_PORT` | `5000` | Server port |
| `USER_DATA_DIR` | `./user_data` | FreqTrade data directory |
| `OPENROUTER_API_KEY` | — | Required for OpenRouter AI |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `FREQTRADE_EXCHANGE` | `binance` | Default exchange |

## Data Formats
- **OHLCV data**: FreqTrade JSON format (`[timestamp, open, high, low, close, volume]`) or `.feather`
- **Backtest results**: FreqTrade ZIP + extracted JSON; parsed into `parsed_results.json`
- **Hyperopt results**: `.fthypt` binary files (FreqTrade format)
- **Conversations**: Plain JSON files (`{conversation_id, messages: [{role, content}], ...}`)
- **Strategy params**: JSON sidecar files alongside `.py` strategy files

## Key Python Patterns
- `pathlib.Path` used throughout (no `os.path` string manipulation)
- `dataclasses` for pipeline result types (`PipelineStep`, `PipelineResult`, `CodeValidation`)
- `asyncio.gather` for parallel AI model calls in debate pipeline
- `AsyncGenerator[dict, None]` for streaming pipeline outputs
- `from __future__ import annotations` for forward references in type hints
- `model_dump()` / `model_dump_json()` (Pydantic v2 API)
- `Field(default_factory=...)` for mutable Pydantic defaults

## Frontend Architecture
- Hash-based SPA routing (`#backtest`, `#ai-diagnosis`, etc.)
- `fetch` API with custom wrapper in `static/js/core/api.js`
- `EventSource` / manual SSE parsing for streaming AI responses
- No external JS libraries (no React, Vue, jQuery)
- CSS custom properties (variables) for theming

## File I/O Conventions
- All JSON reads use `read_json(path, default)` from `app/core/storage.py` — never raises
- All JSON writes use `write_json(path, data)` — auto-creates parent dirs
- Config writes use atomic pattern: `tempfile.mkstemp` → write → `os.replace`
- Directory creation: `path.mkdir(parents=True, exist_ok=True)` at startup in `config.py`
