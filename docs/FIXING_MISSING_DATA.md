# Fixing Missing/Incomplete Data Issues

Last verified: 2026-04-07 (Asia/Riyadh)

## Problem
When running backtests, you may encounter errors like:
```
Missing/incomplete local data for: ETH/USDT. 
ETH/USDT: incomplete days [2026-04-05 (221/288)]
```

This means your local data files are missing or have incomplete candle data for the specified trading pairs.

## Automatic Solution (Recommended)

The system now **automatically downloads missing data** when you try to run a backtest:

1. **Start a backtest** through the UI or API
2. If data is missing, the system will:
   - Automatically trigger a download job for missing pairs
   - Return HTTP 202 with the download job ID
   - Show which pairs are being downloaded
3. **Wait for download to complete** (monitor via UI or API)
4. **Retry your backtest** - it should now work!

### Example API Response
```json
{
  "detail": "Downloading missing data for pairs: ETH/USDT. Download job ID: dl_abc123. Details: ETH/USDT: incomplete days [2026-04-05 (221/288)]. Please wait for download to complete and retry the backtest."
}
```

## Manual Download Options

### Option 1: Using the Download Script

Download specific pairs:
```bash
python scripts/download_missing_data.py --pairs ETH/USDT BTC/USDT --timeframe 5m --timerange 20250102-20260404 --wait
```

Auto-detect missing pairs from config:
```bash
python scripts/download_missing_data.py --auto-detect --timeframe 5m --timerange 20250102-20260404 --wait
```

### Option 2: Using FreqTrade Directly

```bash
# Download specific pair
freqtrade download-data --exchange binance --pairs ETH/USDT --timeframe 5m --timerange 20250102-20260404 --prepend

# Download multiple pairs
freqtrade download-data --exchange binance --pairs ETH/USDT BTC/USDT SOL/USDT --timeframe 5m --timerange 20250102-20260404 --prepend
```

### Option 3: Using the API (current routes)

```bash
# Trigger download via API
curl -X POST http://127.0.0.1:5000/download-data \
  -H "Content-Type: application/json" \
  -d '{
    "pairs": ["ETH/USDT", "BTC/USDT"],
    "timeframe": "5m",
    "timerange": "20250102-20260404"
  }'

# Check download status
curl http://127.0.0.1:5000/download-data/{job_id}
```

## Understanding the Error

### Incomplete Days
`ETH/USDT: incomplete days [2026-04-05 (221/288)]` means:
- **221/288**: Only 221 candles found, but 288 expected for a full day
- For 5-minute timeframe: 1440 minutes/day / 5 = 288 candles/day
- Missing 67 candles for that day

### Common Causes
1. **Partial downloads** - Download was interrupted
2. **Exchange downtime** - Exchange had no data for that period
3. **Current day** - Today's data is still being generated (this is normal)
4. **Wrong timerange** - Check your system date (the error shows 2026, which might be a clock issue)

## Data Validation

Check data coverage before backtesting (current route):
```bash
curl -X POST http://127.0.0.1:5000/data-coverage \
  -H "Content-Type: application/json" \
  -d '{
    "pairs": ["ETH/USDT"],
    "timeframe": "5m",
    "exchange": "binance",
    "timerange": "20250102-20260404"
  }'
```

Response shows:
- `available`: Whether data file exists
- `missing_days`: Days with no data
- `incomplete_days`: Days with partial data
- `expected_candles_per_day`: Expected candle count

## Troubleshooting

### System Clock Issue
If you see dates that do not match your local date:
```bash
# Windows
date
time

# Fix if needed (run as Administrator):
# Set correct date and time/timezone
```

### Data Still Missing After Download
1. Check download logs for errors
2. Verify exchange connectivity
3. Try downloading a smaller timerange
4. Check if the pair is actually traded on the exchange

### Incomplete Current Day
If the incomplete day is today, this is **normal**:
- The current day is still in progress
- The system allows partial data for today
- No action needed

## Configuration

Default download settings in `app/services/command_builder.py`:
- Default start date: `20240101`
- Uses `--prepend` flag to fill gaps
- Downloads to: `user_data/data/{exchange}/`

## File Locations

- **Data files**: `user_data/data/binance/ETH_USDT-5m.*` (json/feather/json.gz depending on setup)
- **Download script**: `scripts/download_missing_data.py`
- **Config**: `user_data/config.json`
- **Backtest results**: `user_data/backtest_results/`
