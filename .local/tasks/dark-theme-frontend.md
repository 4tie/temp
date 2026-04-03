# Dark Theme Frontend Build

## What & Why
Build a complete, polished frontend for the 4tie FreqTrade management UI with a dark theme that uses no blue variants. All template and CSS files are currently empty shells — this task builds them from scratch. The palette centers on near-black backgrounds, warm-to-neutral grays, emerald/green accents for positive signals, amber/orange for warnings and highlights, rose/red for losses/danger, and violet/purple for secondary accents. No blue of any kind.

## Done looks like
- The app loads with a fully styled dark layout: sidebar nav, topbar, status bar, and content area.
- All 8 pages render cleanly: Dashboard, Backtesting, Hyperopt, Strategy Lab, AI Diagnosis, Jobs, Results, Settings.
- Every page uses a consistent dark color system with zero blue variants — greens, ambers, purples, and neutral grays only.
- Typography, spacing, cards, tables, badges, buttons, inputs, modals, tabs, and toasts are all styled and cohesive.
- The sidebar shows active-page highlighting and the layout is responsive.
- JS components (sidebar toggle, tabs, modal, toast) are wired and functional.
- The app runs via uvicorn and is visible in the browser with no layout or styling errors.

## Out of scope
- Backend API changes or new endpoints.
- Chart/graph rendering (placeholder containers are acceptable).
- Mobile breakpoints beyond a functional collapsed sidebar.
- Authentication flow changes.

## Tasks
1. **Color system & base CSS** — Define CSS custom properties for the full dark palette (backgrounds, surfaces, borders, text, accent colors: emerald, amber, violet, rose) in `base.css`. Set base resets, typography (system font stack), and scrollbar styling.

2. **Layout CSS** — Build the three-panel layout in `layout.css`: fixed sidebar (240px), fixed topbar (56px), fixed statusbar (32px at bottom), and scrollable main content area. Include collapsed-sidebar state.

3. **Component CSS** — Style all reusable UI primitives in `components.css`: cards, buttons (primary/secondary/ghost/danger), form inputs and selects, badges/chips, tables, tabs, modals, toast notifications, loading spinners, empty-state blocks, and code blocks.

4. **Page CSS** — Write page-specific styles for all 8 pages in their respective CSS files: Dashboard (metric cards, mini charts), Backtesting (form layout, results panel), Hyperopt (job list, parameter grid), Strategy Lab (file tree, code viewer), AI Diagnosis (analysis card, signal indicators), Jobs (job table, status column), Results (compare table, equity curve placeholder), Settings (form groups, toggle switches).

5. **HTML layout templates** — Build `base.html` (head, CSS/JS links, body wrapper), `sidebar.html` (logo, nav links with icons, collapse button), `topbar.html` (app title, run status pill, action buttons), and `statusbar.html` (connection status, live ticker text).

6. **HTML page templates** — Build all 8 page templates with semantic markup matching the CSS: Dashboard, Backtesting, Hyperopt, Strategy Lab, AI Diagnosis, Jobs, Results, Settings. Use data-attribute hooks the JS can bind to.

7. **JS core wiring** — Implement `app.js` (page router, init lifecycle), `api-client.js` (fetch wrapper with error handling), `dom.js` (query helpers), and `auth.js` (connection check). Wire `sidebar.js` (toggle, active link), `tabs.js`, `modal.js`, and `toast.js` components.

8. **JS page logic** — Implement each page's JS module to load data from the API and render it into the DOM: dashboard stats, backtest form submission and results display, hyperopt job list, strategy file list, jobs table, results compare view, and settings save/load.

9. **Utilities CSS** — Add helper classes in `utilities.css`: spacing, flex/grid shortcuts, text utilities, color utilities, visibility helpers, and truncation.

10. **Workflow setup & verification** — Configure the uvicorn workflow, start the server, verify the app renders correctly with no console errors.

## Relevant files
- `app/main.py`
- `app/routers/backtest.py`
- `app/routers/strategies.py`
- `app/routers/hyperopt.py`
- `templates/layouts/base.html`
- `templates/partials/sidebar.html`
- `templates/partials/topbar.html`
- `templates/partials/statusbar.html`
- `templates/pages/dashboard/index.html`
- `templates/pages/backtesting/index.html`
- `templates/pages/hyperopt/index.html`
- `templates/pages/strategy-lab/index.html`
- `templates/pages/ai-diagnosis/index.html`
- `templates/pages/jobs/index.html`
- `templates/pages/results/index.html`
- `templates/pages/settings/index.html`
- `static/css/base.css`
- `static/css/layout.css`
- `static/css/components.css`
- `static/css/utilities.css`
- `static/css/pages/dashboard.css`
- `static/css/pages/backtesting.css`
- `static/css/pages/hyperopt.css`
- `static/css/pages/strategy-lab.css`
- `static/css/pages/ai-diagnosis.css`
- `static/css/pages/jobs.css`
- `static/css/pages/results.css`
- `static/css/pages/settings.css`
- `static/js/core/app.js`
- `static/js/core/api-client.js`
- `static/js/core/dom.js`
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
- `static/js/utils/state.js`
- `static/js/utils/format.js`
