# Create Missing MultiMa.json Parameter File

## What & Why
Freqtrade automatically looks for `user_data/strategies/MultiMa.json` alongside the strategy `.py` file to load hyperopt parameters. This file was never created (it was missed when Task #12 migrated all other strategy JSON files). Without it, every backtest run for MultiMa aborts immediately with "Invalid parameter file provided."

## Done looks like
- `user_data/strategies/MultiMa.json` exists in the flat Freqtrade-compatible format matching the other strategy files.
- Running a backtest for the MultiMa strategy no longer produces the "Invalid parameter file provided" error.

## Out of scope
- Modifying any other strategy files.
- Changing how the app reads or writes strategy parameters.

## Tasks
1. **Create MultiMa.json** — Create `user_data/strategies/MultiMa.json` as a flat JSON object containing the strategy's default optimizable parameter values (`buy_ma_count`, `buy_ma_gap`, `sell_ma_count`, `sell_ma_gap`), matching the same format as the other strategy JSON files in that directory.

## Relevant files
- `user_data/strategies/MultiMa.py`
- `user_data/strategies/MultiMa2026HoldBase.json`
