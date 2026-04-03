# Remove Collapsible Download Data Card

## What & Why
Task #4 added a "Download Data" button directly in the form action bar, making the separate collapsible Download Data card redundant. The card's three config fields (exchange, timeframe, days) are still needed by the download handler, so they should be moved inline rather than deleted entirely.

## Done looks like
- The collapsible "Download Data" card (with its toggle header, chevron, and expand/collapse behaviour) is gone from both Backtesting and Hyperopt pages.
- The exchange, timeframe, and days fields are displayed as a small, always-visible row directly below the form action buttons (Run / Download Data / Stop).
- The download log panel appears in that same inline area when a download is running.
- The old "Download Data" button that was inside the card (`bt-dl-btn` / `ho-dl-btn`) is removed; the form-action button (`bt-dl-form-btn`) is the only trigger.
- No JS toggle logic, badge, or chevron references remain.
- The status badge that was in the card header (bt-dl-badge / ho-dl-badge) is removed.

## Out of scope
- Changing how `_onDownload()` works internally.
- Any changes to the `/download-data` API.
- Hyperopt-specific fields (only exchange/timeframe/days are shared with backtesting).

## Tasks
1. **Backtesting cleanup** — Remove the collapsible card HTML, move exchange/timeframe/days + log panel into an always-visible inline section below the action buttons. Remove `bt-dl-btn`, `bt-dl-badge`, `bt-dl-chevron`, `bt-dl-toggle`, and `bt-dl-body` from both the HTML template and all JS references (`dlToggle`, `dlChevron`, `dlBody`, `dlBtn`, `badge` update calls).

2. **Hyperopt cleanup** — Same as above for the Hyperopt page: remove collapsible card, move fields inline, remove `ho-dl-btn`, `ho-dl-badge`, `ho-dl-chevron`, `ho-dl-toggle`, `ho-dl-body` from HTML and JS.

## Relevant files
- `static/js/pages/backtesting.js`
- `static/js/pages/hyperopt.js`
