# Simplify Download Data Command

## What & Why
Remove the DL Exchange, DL Timeframe, and Days fields from the Download Data section on both the Backtesting and Hyperopt pages. The download command should mirror the run backtest config — using the config file, reading timeframe from the main run form, and a fixed timerange — instead of requiring separate inputs.

## Done looks like
- The "DL Exchange", "DL Timeframe", and "Days" fields are gone from both pages
- Clicking "Download Data" generates the command: `python -m freqtrade download-data -c user_data/config.json --timeframe 5m --timerange 20251001-20260321 --pairs {selected pairs}`
- Timeframe is taken from the main backtest/hyperopt form (same value used for Run Backtest)
- No exchange or days are sent to or used by the backend

## Out of scope
- Changing how pairs are selected
- Modifying the Run Backtest or Hyperopt commands
- Making timerange or timeframe configurable from the UI

## Tasks
1. **Remove DL fields from UI** — Delete the DL Exchange, DL Timeframe, and Days form groups from both the Backtesting and Hyperopt page templates.
2. **Update frontend download logic** — In `_onDownload()` on both pages, read timeframe from the main run form field instead of the now-removed DL Timeframe field, and stop sending `exchange` and `days` to the API.
3. **Update the backend command builder** — Change `build_download_data_command` to use `python -m freqtrade download-data` with `-c user_data/config.json`, `--timeframe`, and `--timerange 20251001-20260321`. Remove all `--exchange` and `--days` logic.
4. **Update schema and router** — Remove `exchange` and `days` from `DownloadDataRequest`. Update the `/download-data` route to stop passing those fields to the command builder.

## Relevant files
- `static/js/pages/backtesting.js:248-284,468-491`
- `static/js/pages/hyperopt.js:258-293,416-439`
- `app/services/command_builder.py:46-73`
- `app/schemas/backtest.py:17-22`
- `app/routers/backtest.py:93-104`
