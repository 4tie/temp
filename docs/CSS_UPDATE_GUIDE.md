# CSS Update Guide

## Changes Made

### 1. Fixed Result Explorer Layout
- **File**: `static/css/pages/results.css`
- **Changes**:
  - Hero section now uses vertical layout
  - Larger title (text-2xl, bold)
  - Metadata badges with background and borders
  - Responsive stat cards (auto-fit grid)
  - Larger stat values (text-xl)
  - Hover effects on stat cards
  - Better mobile responsiveness

### 2. Cache Busting
- **File**: `templates/layouts/base.html`
- Added version parameter: `results.css?v=20260406`

### 3. No-Cache Middleware
- **File**: `app/main.py`
- Added `NoCacheMiddleware` to prevent CSS caching during development
- CSS files now served with `Cache-Control: no-cache` headers

## How to See Changes

### Option 1: Hard Refresh Browser
- **Windows/Linux**: `Ctrl + Shift + R` or `Ctrl + F5`
- **Mac**: `Cmd + Shift + R`

### Option 2: Clear Browser Cache
1. Open DevTools (F12)
2. Right-click refresh button
3. Select "Empty Cache and Hard Reload"

### Option 3: Restart Server
```bash
python run.py stop
python run.py
```

The middleware will now prevent CSS caching automatically.

## Verify Changes

1. Open browser DevTools (F12)
2. Go to Network tab
3. Filter by CSS
4. Refresh page
5. Check `results.css` response headers:
   - Should see `Cache-Control: no-cache, no-store, must-revalidate`

## CSS Structure

```
static/css/pages/results.css
├── .result-explorer__hero (vertical layout)
│   ├── .result-explorer__hero-main (title + metadata)
│   └── .result-explorer__hero-stats (responsive grid)
├── .result-explorer__hero-stat (individual stat cards)
├── .result-explorer__tabs (horizontal scrollable)
└── .tab-panel (content sections)
```

## Key CSS Variables Used

- `--space-3`, `--space-4`, `--space-5`: Spacing
- `--text-xl`, `--text-2xl`: Font sizes
- `--font-bold`, `--font-semibold`: Font weights
- `--border-subtle`, `--border`: Border colors
- `--surface-1`, `--surface-2`: Background colors
- `--text-primary`, `--text-muted`: Text colors

## Responsive Breakpoints

- **Desktop**: Auto-fit grid (min 140px per card)
- **Tablet** (< 1100px): Auto-fit grid (min 120px per card)
- **Mobile** (< 720px): 2 columns, smaller fonts
