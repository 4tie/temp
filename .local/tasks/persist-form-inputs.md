# Persist All Form Inputs Across Reloads

## What & Why
All user-entered values in the Backtesting and Hyperopt forms are lost on every page refresh or app restart. Users want their strategy, exchange, timeframe, timerange, wallet, pairs selection, and other settings remembered automatically without clicking Save.

## Done looks like
- On the Backtesting page, every field (strategy, exchange, timeframe, timerange, wallet, max open trades, stake amount, download exchange/timeframe/days) and the pairs selection are restored exactly as the user left them after any page refresh or server restart.
- On the Hyperopt page, every field (strategy, exchange, loss function, spaces checkboxes, epochs, jobs, timeframe, timerange, wallet, min trades, download exchange/timeframe/days) and the pairs selection are restored.
- Changes are saved automatically as the user edits — no Save button required.
- Pairs checked in the picker are restored once the picker finishes loading.

## Out of scope
- Dashboard, Strategy Lab, Results, Jobs, AI Diagnosis (no significant form inputs)
- Settings page (already persists via existing localStorage logic)
- Server-side storage (localStorage only — no new API endpoints)

## Tasks
1. **Backtesting form persistence** — Add `_saveForm()` / `_loadSavedForm()` helpers using localStorage key `4tie_bt_form`. Wire `change`/`input` events on all form fields (including the download panel) to auto-save. Save selected pair names on checkbox change. Restore non-dynamic fields immediately on init; pass saved pair names as the `preSelected` list to `_loadPairs()` so they are re-checked once the picker renders.

2. **Hyperopt form persistence** — Same approach with key `4tie_ho_form`. Covers all Hyperopt-specific fields: loss function select, spaces checkboxes (stored as an array), epochs, jobs, min trades, and the download panel fields. Restore on init; pass saved pairs as preSelected.

## Relevant files
- `static/js/pages/backtesting.js`
- `static/js/pages/hyperopt.js`
