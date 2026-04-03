# Live Command Preview & Config.json Sync

## What & Why
Three things need to happen together:

1. **Command preview before running**: The coloured command block should appear as soon as the page loads and update live whenever the user changes any field — no need to run first to see it.
2. **Correct command format**: The actual command that FreqTrade runs (and the preview shown) must use `python -m freqtrade backtesting -c user_data/config.json` without extra flags that are already covered by the config file.
3. **Live config.json write-back**: Strategy, Max Open Trades, Starting Wallet, and Stake Amount fields must read their initial values from `user_data/config.json` and write any change back to that file instantly.

## Done looks like
- The coloured command block is visible in the Configuration card **before** clicking Run, showing the exact command that will be run.
- It updates instantly as the user changes strategy, timeframe, timerange, or pairs.
- The command format is exactly:
  ```
  python -m freqtrade backtesting -c user_data/config.json --timeframe 5m --export trades --export-filename user_data/backtest_results/<strategy>/result.json --timerange 20251001-20260321 --pairs ETH/USDT BTC/USDT
  ```
- `--strategy`, `--dry-run-wallet`, `--max-open-trades`, `--stake-amount`, `--userdir`, `--datadir`, `--strategy-path` are absent from both the preview and the command that actually runs.
- Strategy, Max Open Trades, Starting Wallet, and Stake Amount fields load from `user_data/config.json` on page load (taking priority over localStorage).
- Editing any of those four fields writes immediately to `user_data/config.json` with a brief "Saved" indicator.
- The command block wraps long lines (word-wrap) rather than scrolling horizontally.

## Out of scope
- Hyperopt page (separate task if needed)
- Download Data command
- Run snapshot history (deferred)
- Settings page

## Tasks

1. **`GET /config` and `PATCH /config` backend endpoints** — Add to `app/routers/backtest.py`:
   - `GET /config`: read `user_data/config.json`, return `{ strategy, max_open_trades, dry_run_wallet, stake_amount, timeframe, exchange }`.
   - `PATCH /config`: accept a partial body with any of those fields, merge into `user_data/config.json`, write atomically, return the updated fields.

2. **Simplified backtest command builder** — In `app/services/command_builder.py`, rewrite `build_backtest_command()` to:
   - Use `["python", "-m", "freqtrade", "backtesting"]`.
   - Use `["-c", "user_data/config.json"]` (relative path).
   - Remove `--userdir`, `--strategy`, `--dry-run-wallet`, `--max-open-trades`, `--stake-amount`, `--datadir`, `--strategy-path`.
   - Keep `--timeframe`, `--export trades`, `--export-filename user_data/backtest_results/{strategy}/result.json`, `--timerange` (if set), `--pairs`.
   - In `app/services/runner.py`, use strategy name as run directory (`BACKTEST_RESULTS_DIR / strategy`), substitute `{strategy}` in the command. Remove `dry_run_wallet`, `max_open_trades`, `stake_amount` parameters from `start_backtest()` — read them from `config.json` inside the function for metadata only. Update `BacktestRequest` schema and `POST /run` endpoint to match.

3. **Live command preview in the UI** — In `static/js/pages/backtesting.js`:
   - Move `#bt-cmd` div to just above the Run/Download buttons inside the Configuration card.
   - Add `_buildLiveCommand()`: reads current form values (strategy, timeframe, timerange, selected pairs) and assembles the command array in the new format.
   - Add `_refreshCommandPreview()`: calls `_buildLiveCommand()` and passes it to the existing `_renderCommandBlock()`.
   - Call `_refreshCommandPreview()` on page init (after form populates) and wire it to `change`/`input` events on strategy, timeframe, timerange, and pairs-list checkbox changes.

4. **Live config sync for four fields** — Still in `backtesting.js`:
   - On init call `GET /config` (new `API.getConfig()`), populate `#bt-strategy`, `#bt-wallet`, `#bt-max-trades`, `#bt-stake` (overrides localStorage).
   - Add `change` listeners on those four fields to call `PATCH /config` (`API.patchConfig(data)`) and show a "Saved" indicator on success.
   - Remove those four fields from the `POST /run` request body.
   - Add `getConfig()` and `patchConfig(data)` to `static/js/core/api-client.js`.

5. **Word-wrap in command block** — In `static/css/components.css`, change `.cmd-block__pre` from `white-space: pre; overflow-x: auto` to `white-space: pre-wrap; word-break: break-all` so the command wraps rather than scrolls.

## Relevant files
- `app/services/command_builder.py`
- `app/services/runner.py`
- `app/routers/backtest.py`
- `app/schemas/backtest.py`
- `static/js/pages/backtesting.js`
- `static/js/core/api-client.js`
- `static/css/components.css`
- `user_data/config.json`
