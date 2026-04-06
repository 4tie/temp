# CSS Update Guide

Last verified: 2026-04-07 (Asia/Riyadh)

## Current cache behavior

### No-cache middleware
- File: `app/main.py`
- `NoCacheMiddleware` is active and applies no-cache headers for `/static/css/*`.
- Expected headers for CSS responses:
  - `Cache-Control: no-cache, no-store, must-revalidate`
  - `Pragma: no-cache`
  - `Expires: 0`

## How to verify CSS updates
1. Open DevTools (`F12`)
2. Go to `Network` tab
3. Filter by `css`
4. Hard refresh page
5. Inspect response headers for CSS files

## Quick refresh options
- Windows/Linux: `Ctrl + Shift + R` or `Ctrl + F5`
- Mac: `Cmd + Shift + R`

## Server commands (current CLI)
`run.py` supports `start`, `status`, and `logs`.

```bash
python run.py start --no-reload --host 127.0.0.1 --port 5000
python run.py status
python run.py logs --lines 100
```

## Results CSS structure (current)
```
static/css/pages/results.css
|- .result-explorer__hero
|  |- .result-explorer__hero-main
|  `- .result-explorer__hero-stats
|- .result-explorer__hero-stat
|- .result-explorer__tabs
`- .tab-panel
```

## Notes
- If updates do not appear, check browser cache and confirm CSS headers first.
- If headers are correct but styles still look stale, verify the server is running the intended workspace path.
