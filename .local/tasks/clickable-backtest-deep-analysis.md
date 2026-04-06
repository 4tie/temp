# Clickable Backtest Deep Analysis View

## What & Why
Every backtest run row across the dashboard (and results page) should be clickable and open a dedicated full-page deep analysis report. The report is structured in clearly labelled phases, each going into maximum depth on a different aspect of the run — from high-level overview down to individual trades, idle gaps, risk patterns, and exact strategy configuration. This gives the user a complete picture of any run without leaving the app.

## Done looks like
- Clicking any row in "Recent Backtest Runs" on the dashboard navigates to (or opens) a rich analysis view for that run
- The analysis view has clearly separated phases the user can scroll through or tab between
- **Phase 1 — Executive Summary**: Strategy name, timeframe, pairs list, exchange, date range, total duration of the test, command used, and all top-level KPIs (total trades, profit %, absolute profit, win rate, loss rate, draw rate, max drawdown %, Sharpe ratio, Sortino ratio, Calmar ratio, starting balance, final balance, avg trade duration, best trade, worst trade, expectancy)
- **Phase 2 — Equity Curve & Balance Timeline**: A line chart of account balance over every day of the backtest, clearly showing growth, dips, and flat periods. Drawdown is overlaid or shown as a second chart beneath it. Each data point is labelled with the date.
- **Phase 3 — Trade-by-Trade Log**: A complete, paginated (or scrollable) table of every single trade: pair, direction (long/short), open date & time, close date & time, hold duration (human-readable), entry price, exit price, profit %, absolute profit, exit reason, MAE, MFE. Rows are color-coded green (win) / red (loss) / grey (draw). Sortable by any column.
- **Phase 4 — Calendar & Gap Analysis**: A visual month-grid calendar covering the full backtest date range. Each day is colored by trade activity (many trades = darker green, few = lighter green, zero = visually distinct "gap" color). Below the calendar, a table lists all consecutive gap periods (date from → date to, number of idle days, what day of week the gap started/ended). This makes silent strategy periods instantly visible.
- **Phase 5 — Per-Pair Deep Dive**: Extended table per trading pair showing: total trades, wins, losses, draws, win rate %, profit sum (abs), profit % mean per trade, best single trade %, worst single trade %, average trade duration, total time in market.
- **Phase 6 — Exit Reason Breakdown**: Bar chart or table showing how trades closed — by reason (e.g. roi, stop_loss, trailing_stop, force_exit, custom_exit). For each reason: count, % of total trades, avg profit %, total profit abs.
- **Phase 7 — Risk & Streak Analysis**: Longest winning streak and losing streak (dates + trade count + profit for each). Average consecutive wins/losses. Avg win size vs avg loss size. Risk/reward ratio. Recovery factor. Profit factor. Max consecutive losses.
- **Phase 8 — Strategy Configuration**: Displays the exact meta configuration used for this run: pairs, timeframe, timerange, exchange, stake amount, max open trades, strategy parameters/JSON. Shown as a clean structured display, not raw JSON dump.
- All phases are accessible either via sticky tabs at the top or by simply scrolling, with section anchors
- A "Back" button returns the user to wherever they came from (dashboard or results page)
- If a run has no parsed results (e.g. failed/running), relevant phases show a graceful "No data available for this run" message rather than crashing

## Out of scope
- Interactive chart editing or custom date range filtering within the analysis view
- Exporting the analysis as PDF or image
- Comparing two runs side-by-side within this view
- Any hyperopt run detail (backtest runs only)

## Tasks
1. **Backend: ensure full run data API** — Verify the `GET /api/runs/{run_id}` endpoint returns all needed fields (trades list with MAE/MFE, equity_curve daily data, per_pair extended stats, exit reasons). Extend the canonical results stack under `app/services/results/` (`result_service.py`, normalizers/builders) and the route to include gap analysis data (a list of idle day ranges) and any missing streak/risk metrics computed server-side. The legacy parser shim is not the canonical entrypoint now.

2. **Frontend: analysis page scaffold** — Create a new page module (`static/js/pages/analysis.js`) and its HTML template (`templates/pages/analysis/index.html`). Register it in the router so navigating to `/analysis/{run_id}` loads it. The page fetches the run via API and renders all 8 phases in order with a sticky tab bar at the top.

3. **Phase 1 — Executive Summary section** — Implement the summary panel: two rows of KPI cards covering all metrics listed above, plus a metadata block showing strategy, pairs, timeframe, timerange, exchange, and date range. Color-code profit metrics green/red.

4. **Phase 2 — Equity & Drawdown charts** — Render a line chart of daily balance over time and a separate drawdown chart beneath it using the equity_curve data. Use the existing charting library already present in the project (or a lightweight canvas/SVG approach). Label axes with dates.

5. **Phase 3 — Full trade log table** — Render the complete trades list as a sortable, color-coded table with all trade fields. Include pagination or virtual scrolling for large trade sets. Make columns sortable client-side.

6. **Phase 4 — Calendar & gap analysis section** — Build a month-grid calendar UI covering the full backtest date range. Color each day by trade count (gradient from no-trade grey to high-trade green). Below the calendar, render a table of all detected idle/gap periods with their start date, end date, and idle day count.

7. **Phase 5 through 8 — Remaining analysis sections** — Implement the per-pair deep dive table, exit reason breakdown (bar visualization + table), risk & streak analysis computed from the trades list, and the strategy configuration display.

8. **Dashboard & results page: make rows clickable** — Add `data-run-id` and click handlers to the `_renderRunsTable` function in `dashboard.js` and the results table in `results.js` so clicking any row navigates to `/analysis/{run_id}`. Style rows with a hover cursor to signal they are clickable.

## Relevant files
- `static/js/pages/dashboard.js`
- `static/js/pages/results.js`
- `templates/pages/dashboard/index.html`
- `templates/pages/results/index.html`
- `app/services/results/result_service.py`
- `app/services/results/trade_normalizer.py`
- `app/services/results/risk_normalizer.py`
- `app/routers/backtest.py`
- `templates/layouts/base.html`
