---
title: Frontend JS — wire to Python backend
---
# Frontend JS — Wire to Python Backend

## What & Why
Phase 1 built the dark-theme HTML/CSS shell (sidebar, topbar, statusbar, layout). This task wires the frontend to the FastAPI backend by implementing all JavaScript files: core utilities, page router, API client, UI components (sidebar toggle, tabs, modal, toast), and per-page data logic. At the end the app is fully interactive — navigating between pages, loading real data from the API, and reflecting live state.

## Done looks like
- Clicking any sidebar link switches the visible page and updates the topbar title, with no full-page reload.
- The sidebar collapse button shrinks/expands the sidebar and persists the state in localStorage.
- The statusbar shows live connection status (green = OK, red = offline) based on polling `/healthz`.
- Dashboard shows a summary of recent backtest runs (count, latest run name/status).
- Backtesting page loads strategies and pairs from the API, lets the user submit a backtest, polls for status, and displays results.
- Hyperopt page loads strategies and pairs, lets the user configure and start a hyperopt run, shows live progress and completed results.
- Strategy Lab lists all strategy files; clicking one shows its parameters.
- Jobs page lists all active/recent runs (backtest + hyperopt) with status badges.
- Results page lists completed backtest runs with key metrics.
- Settings page loads and saves the last-used configuration.
- Toast notifications appear on success/error for all actions.
- No blue colors are used in any JS-generated DOM.

## Out of scope
- Chart rendering (equity curves, OHLCV charts) — placeholder containers only.
- AI Diagnosis page — placeholder content (no AI integration yet).
- Authentication / login flow.
- Compare page (multi-run comparison).

## Tasks

1. **Core utilities** — Implement `format.js` (currency, percentage, date, duration helpers) and `state.js` (lightweight reactive store: `get`, `set`, `subscribe`). These are pure functions with no DOM dependencies.

2. **API client** — Implement `api-client.js`: base URL auto-detected from `window.location`, a `request(method, path, body)` wrapper with JSON handling and error bubbling, and named shorthand exports for every backend endpoint (`getStrategies`, `getRuns`, `startBacktest`, `getHyperoptRuns`, `startHyperopt`, etc.).

3. **DOM helpers** — Implement `dom.js`: `$`, `$$`, `on`, `once`, `show`, `hide`, `addClass`, `removeClass`, `toggleClass`, `createElement`, `setHTML`, `setText` utilities used throughout the app.

4. **App bootstrap & router** — Implement `app.js`: hash-based page router (`#dashboard`, `#backtesting`, etc.), shows the correct `.page-view`, updates the active `.sidebar__link`, sets the topbar page title, and calls each page module's `init()` on first visit. Also implement `auth.js`: polls `/healthz` every 5 seconds, updates the statusbar connection dot and label, and updates the topbar status pill.

5. **Sidebar & shared components** — Implement `sidebar.js` (collapse toggle, active-link management, jobs badge count update), `tabs.js` (tab group switching via `data-tab` / `data-tab-panel` attributes), `modal.js` (open/close by ID with keyboard trap and backdrop click), `toast.js` (show/dismiss with type: success/error/warning/info, auto-dismiss after 4 s).

6. **Dashboard page** — `dashboard.js`: on init, fetch `/runs` and `/hyperopt/runs`, render summary cards (total runs, last run name + status, last hyperopt run). Keep it light — no charts, just numbers and status badges.

7. **Backtesting page** — `backtesting.js`: populate strategy select from `/strategies`, populate pair multi-select from `/pairs`, restore last config from `/last-config`. On submit: POST to `/run`, poll `/runs/{run_id}` every 2 s, stream logs to a log panel, display results table when complete. Delete run button calls `DELETE /runs/{run_id}`.

8. **Hyperopt page** — `hyperopt.js`: populate strategy and pair selects, populate loss function and spaces selects from `/hyperopt/loss-functions` and `/hyperopt/spaces`. On submit: POST to `/hyperopt/run`, poll for progress (epoch count, best profit), show completed results table. Apply-params button calls `/hyperopt/apply-params`.

9. **Strategy Lab page** — `strategy-lab.js`: fetch `/strategies`, render a clickable list of strategy files. On select: fetch `/strategies/{name}/params` and render a parameter table (name, type, default, description).

10. **Jobs page** — `jobs.js`: fetch both `/runs` and `/hyperopt/runs`, merge into a unified list sorted by recency, render a table with run ID, type (backtest/hyperopt), strategy, status badge, and start time. Polling every 5 s while any job is running. Update the sidebar jobs badge with the count of active jobs.

11. **Results page** — `results.js`: fetch `/runs`, filter to completed runs, render a sortable table with key metrics (profit %, Sharpe, drawdown, trade count, win rate). Clicking a row shows the full result detail in a modal or expanded panel.

12. **Settings page** — `settings.js`: fetch `/last-config`, populate form fields (exchange, timeframe, wallet size, max open trades, stake amount, data directory). On save: store values to localStorage. Fetch and display presets from `/presets`, allow saving the current config as a named preset and deleting existing ones.

## Relevant files
- `static/js/utils/format.js`
- `static/js/utils/state.js`
- `static/js/core/api-client.js`
- `static/js/core/dom.js`
- `static/js/core/app.js`
- `static/js/core/auth.js`
- `static/js/components/sidebar.js`
- `static/js/components/tabs.js`
- `static/js/components/modal.js`
- `static/js/components/toast.js`
- `static/js/pages/dashboard.js`
- `static/js/pages/backtesting.js`
- `static/js/pages/hyperopt.js`
- `static/js/pages/strategy-lab.js`
- `static/js/pages/ai-diagnosis.js`
- `static/js/pages/jobs.js`
- `static/js/pages/results.js`
- `static/js/pages/settings.js`
- `app/routers/backtest.py`
- `app/routers/hyperopt.py`
- `app/routers/strategies.py`
- `app/routers/presets.py`
- `app/routers/compare.py`
- `templates/pages/dashboard/index.html`
- `templates/pages/backtesting/index.html`
- `templates/pages/hyperopt/index.html`
- `templates/pages/strategy-lab/index.html`
- `templates/pages/ai-diagnosis/index.html`
- `templates/pages/jobs/index.html`
- `templates/pages/results/index.html`
- `templates/pages/settings/index.html`
- `static/css/components.css`
- `static/css/utilities.css`