# Simplify Backtest Command & Live Config Write-back

## What & Why
Two related changes:

1. **Simpler command**: The FreqTrade command that gets run should be minimal — it only needs the config file, timeframe, timerange, pairs, and export paths. All wallet/trades/stake settings come from `user_data/config.json` via `-c`.

2. **Live config write-back**: Max Open Trades, Starting Wallet, Stake Amount, and Strategy fields in the Backtesting form should read directly from `user_data/config.json` and write back to it instantly on change (no separate "Save" step).

3. **Run snapshots**: Every backtest run stores a full parameter snapshot alongside the result so the user can restore the exact config, pairs, and settings used in any past run.

## Done looks like
- The command logged and shown in the UI matches:
  ```
  python -m freqtrade backtesting -c user_data/config.json \
    --timeframe 5m \
    --export trades \
    --export-filename user_data/backtest_results/<strategy>/result.json \
    --timerange 20251001-20260321 \
    --pairs ETH/USDT
  ```
- `--strategy`, `--dry-run-wallet`, `--max-open-trades`, `--stake-amount`, `--userdir`, `--datadir`, `--strategy-path` are all gone from the command (they come from config.json).
- `result.json` is always at `user_data/backtest_results/<strategy>/result.json` — overwritten each run.
- Every run also writes a timestamped snapshot file at `user_data/backtest_results/<strategy>/snapshots/<YYYYMMDD_HHMMSS>_snapshot.json` containing: strategy, pairs, timeframe, timerange, and a full copy of the config fields active at run time (max_open_trades, dry_run_wallet, stake_amount, exchange).
- The Recent Runs history table shows each snapshot as a row (multiple rows per strategy, one per run), with strategy, pairs count, timeframe, timerange, date, and a "Restore" button.
- Clicking "Restore" on a snapshot writes those saved values back to `user_data/config.json` and re-populates the form fields instantly, confirming with a toast.
- Changing Strategy, Max Open Trades, Wallet, or Stake Amount in the form immediately writes to `user_data/config.json`. No separate save button. A brief "Saved" indicator appears near the field.
- On page load, all four fields are populated from `user_data/config.json`.

## Out of scope
- Hyperopt command (separate task if needed)
- Changing how pairs, timeframe, or timerange are handled
- Download Data command
- Settings page

## Tasks

1. **New `GET /config` + `PATCH /config` endpoints** — Add two endpoints to `app/routers/backtest.py`:
   - `GET /config` reads `user_data/config.json` and returns `strategy`, `max_open_trades`, `dry_run_wallet`, `stake_amount`, `timeframe`, `exchange`.
   - `PATCH /config` accepts any subset of those fields, merges them into `user_data/config.json`, and writes the file atomically.

2. **Simplified command builder** — Update `app/services/command_builder.py` `build_backtest_command()` to:
   - Use `sys.executable -m freqtrade` instead of `freqtrade`.
   - Use `-c user_data/config.json` (relative path, short flag) instead of `--config <absolute>`.
   - Remove `--userdir`, `--strategy`, `--dry-run-wallet`, `--max-open-trades`, `--stake-amount`, `--datadir`, `--strategy-path`.
   - Export filename template: `user_data/backtest_results/{strategy}/result.json`.

3. **Runner, storage, and snapshots** — Update `app/services/runner.py` `start_backtest()` to:
   - Use strategy name as the run directory (`run_dir = BACKTEST_RESULTS_DIR / strategy`).
   - Replace `{strategy}` placeholder in the command.
   - After launching, write a timestamped snapshot file to `user_data/backtest_results/<strategy>/snapshots/<YYYYMMDD_HHMMSS>_snapshot.json` capturing all active parameters (strategy, pairs, timeframe, timerange, max_open_trades, dry_run_wallet, stake_amount, exchange).
   - Remove `dry_run_wallet`, `max_open_trades`, `stake_amount` from `start_backtest()` parameters (read them from `config.json` inside the function instead).
   - Update `BacktestRequest` schema and `POST /run` endpoint accordingly.
   - Add a `GET /snapshots` endpoint that lists all snapshot files across all strategies, sorted newest-first, returning each snapshot's metadata fields.
   - Add a `POST /snapshots/restore` endpoint that accepts a snapshot's data and calls `PATCH /config` to apply it.

4. **Frontend live config sync + snapshot history** — In `static/js/pages/backtesting.js`:
   - On init, call `GET /config` to populate strategy, max_open_trades, dry_run_wallet, stake_amount fields (takes priority over localStorage for these four).
   - Add `change` listeners on those four fields that call `PATCH /config` immediately. Show a brief "Saved to config" indicator on success.
   - Remove those four fields from the `POST /run` request body.
   - Replace the "Recent Runs" table with a snapshot history table: columns for Strategy, Pairs, Timeframe, Timerange, Date, and a "Restore" button. Load from `GET /snapshots` on init and after each run.
   - "Restore" calls `POST /snapshots/restore`, then re-populates the form fields from the restored values and shows a success toast.
   - Add `getConfig()`, `patchConfig(data)`, `getSnapshots()`, and `restoreSnapshot(data)` to `static/js/core/api-client.js`.

## Relevant files
- `app/services/command_builder.py`
- `app/services/runner.py`
- `app/routers/backtest.py`
- `app/schemas/backtest.py`
- `app/core/config.py`
- `static/js/pages/backtesting.js`
- `static/js/core/api-client.js`
- `user_data/config.json`
