# Guard Against Invalid Strategy Parameter JSON

## What & Why
FreqTrade loads `user_data/strategies/{strategy}.json` before every backtest or hyperopt run. If that file exists but contains non-flat or malformed JSON (e.g. nested dicts, empty bytes, or old migration artefacts), FreqTrade exits immediately with "Invalid parameter file provided" and the run fails.

This happened with `MultiMa.json` (Apr 3 16:06:29 run). The file was cleaned up but the root vulnerability remains: any strategy with a corrupted param file will always fail without any useful explanation to the user.

## Done looks like
- Before launching the FreqTrade subprocess, the runner validates `user_data/strategies/{strategy}.json`.
- If the file is missing → do nothing (FreqTrade uses class defaults, which is correct).
- If the file exists and is a valid flat dict (`{str: scalar}`) → do nothing, leave it as-is.
- If the file exists but is invalid (nested values, non-dict, unparseable JSON, empty) → overwrite it with `{}` so FreqTrade uses class defaults and the run proceeds.
- A warning is appended to the run's log output whenever a file is auto-corrected.
- `MultiMa.json` is created as `{}` (if absent) so the strategy always has a valid baseline.

## Out of scope
- Changing how hyperopt writes param files (that path is correct already)
- Re-running the full migration script
- Hyperopt page changes

## Tasks
1. **Pre-run JSON guard in runner** — In `app/services/runner.py`, before `_run_subprocess()` in `start_backtest()`, add a helper `_ensure_valid_strategy_json(strategy, run_id)` that: reads `STRATEGIES_DIR / f"{strategy}.json"` if it exists, checks it is a `dict` with no nested-dict values, and if invalid writes `{}` to the file and appends a warning line to the run log.

2. **Create missing MultiMa.json** — Write `user_data/strategies/MultiMa.json` as `{"buy_ma_count": 4, "buy_ma_gap": 8, "sell_ma_count": 12, "sell_ma_gap": 68}` (the default values from `MultiMa.py`'s `buy_params` and `sell_params`). This matches the flat format FreqTrade expects.

## Relevant files
- `app/services/runner.py`
- `user_data/strategies/MultiMa.py`
- `user_data/strategies/MultiMa.json` (to be created)
