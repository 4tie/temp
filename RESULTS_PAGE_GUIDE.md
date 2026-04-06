# Results Page - Quick Reference

## Page Location
Navigate to: **Results** (from sidebar)

## Main Features

### 1. Results Table
Displays all completed backtest runs with key metrics.

**Columns:**
- Run ID (truncated)
- Strategy / Version
- Date (started)
- Profit % (color-coded)
- Win Rate (color-coded)
- Trades
- Drawdown (color-coded)
- Other metrics (configurable)
- Actions (View, Apply buttons)

**Interactions:**
- Click column header → Sort by that column
- Click row → Open result explorer
- Click "View" → Open result explorer
- Click "Apply" → Apply run configuration to current settings

### 2. Result Explorer Modal

**Tabs:**

1. **Overview** - Complete performance summary
   - Performance metrics (profit, win rate, ratios)
   - Wallet & exposure details
   - Risk metrics (drawdown, consecutive wins/losses)
   - Run metadata
   - Strategy runtime settings

2. **Intelligence** - AI-powered insights
   - Primary diagnosis
   - Detected issues
   - Quick parameter actions
   - Manual guidance
   - Comparison to parent run

3. **Charts** - Visual analysis
   - Cumulative profit line chart
   - Daily profit bar chart
   - Drawdown line chart
   - Monthly aggregate bar chart

4. **Trades** - Individual trade details
   - Filterable by pair, tag, exit, direction
   - Paginated (25 per page)
   - Sortable columns
   - Shows MAE/MFE, duration, profit

5. **Per Pair** - Performance by trading pair
   - Filterable and sortable
   - Shows trades, profit, win rate, drawdown, etc.

6. **Tags & Exits** - Breakdown by tags
   - Exit reason summary
   - Enter tag summary
   - Mixed tag stats
   - Left open trades

7. **Periods** - Time-based analysis
   - Daily, weekly, monthly, yearly breakdowns
   - Weekday analysis
   - Charts and tables

8. **Diagnostics** - Technical details
   - Rejected signals
   - Canceled/replaced orders
   - Warnings
   - Locks
   - Run metadata
   - Command used

9. **Data Integrity Warnings** - Data quality issues
   - Missing metrics
   - Corrected mismatches

10. **Raw** - Raw JSON data
    - Copy to clipboard
    - Shows data source
    - Full payload

**Actions in Modal:**
- "Apply Run Config" → Apply settings to backtesting page
- "Improve & Re-run" → Navigate to backtesting with intelligence

### 3. Auto-Features

**Auto-Refresh:**
- Polls every 5 seconds when page is active
- Shows last updated timestamp
- Silent updates (no loading spinner)

**Auto-Open:**
- Automatically opens latest completed run
- Only opens once per new run
- Respects user navigation

## Color Coding

### Metrics
- **Green** → Positive/Good (profit > 0, high win rate)
- **Red** → Negative/Bad (loss, high drawdown)
- **Amber** → Warning/Medium severity
- **Muted** → Neutral/Zero

### Intelligence Severity
- **Red** → Critical/High severity issues
- **Amber** → Warning/Medium severity issues
- **Green** → OK/Low severity issues

## Keyboard Shortcuts

- **Esc** → Close result explorer modal
- **Mouse wheel** on tabs → Scroll tab strip horizontally

## Tips

1. **Sorting**: Click column headers multiple times to toggle ascending/descending
2. **Filtering**: Use search boxes in tabs to filter data
3. **Charts**: Hover over charts to see values (if interactive)
4. **Quick Apply**: Use "Apply" button for fast configuration updates
5. **Intelligence**: Check Intelligence tab for AI-powered improvement suggestions
6. **Raw Data**: Use Raw tab to export full JSON for external analysis

## Common Workflows

### Compare Runs
1. Open first run in result explorer
2. Note key metrics
3. Close modal
4. Open second run
5. Compare metrics manually
(Future: side-by-side comparison mode)

### Apply Best Configuration
1. Sort by Profit % (descending)
2. Click "Apply" on best run
3. Navigate to Backtesting page
4. Configuration is pre-filled

### Improve Strategy
1. Open run in result explorer
2. Go to Intelligence tab
3. Review suggestions
4. Click "Improve & Re-run"
5. Adjust parameters on Backtesting page
6. Run new backtest

### Export Data
1. Open run in result explorer
2. Go to Raw tab
3. Click "Copy JSON"
4. Paste into external tool

## Troubleshooting

**No results showing:**
- Check if any backtests have completed
- Refresh page manually
- Check browser console for errors

**Modal won't open:**
- Check if run_id is valid
- Refresh page
- Check network tab for API errors

**Metrics not displaying:**
- Check if result has metrics data
- Verify metric registry loaded
- Check Raw tab for data availability

**Auto-refresh not working:**
- Ensure page is active (not in background)
- Check browser console for errors
- Manually refresh to restart polling
