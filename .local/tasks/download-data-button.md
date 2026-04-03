# Add Download Data Button to Form

## What & Why
Add a standalone "Download Data" button directly in the backtest form's action bar, next to the existing "Run Backtest" button. Currently the download functionality is hidden inside a collapsible card below the form, making it easy to miss. Surfacing it as a primary action improves discoverability.

## Done looks like
- A "Download Data" button appears next to "Run Backtest" in the form actions row
- Clicking it triggers the same download flow as the button in the collapsible card (uses selected pairs, exchange, timeframe, and days from the download card inputs — or sensible defaults if the card hasn't been opened)
- The button shows a loading/disabled state while download is running, just like the existing `bt-dl-btn`
- The collapsible Download Data card remains in place (for its exchange/timeframe/days config inputs and log panel)

## Out of scope
- Removing or hiding the existing collapsible Download Data card
- Redesigning the form layout beyond adding this button

## Tasks
1. **Add the button to the form actions row** — Insert a "Download Data" button (styled `btn--secondary`) into the `.form-actions` div that contains the Run Backtest and Stop buttons, positioned between or alongside them.
2. **Wire the button to the existing download handler** — Attach a click listener to the new button that calls the existing `_onDownload()` function. Also keep both buttons (the new one and `bt-dl-btn`) in sync for disabled/enabled state during a download run.

## Relevant files
- `static/js/pages/backtesting.js:191-197,431-488`
