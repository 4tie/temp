# Fix Strategy JSON Parameter Format

## What & Why
All 24 strategy `.json` files in `user_data/strategies/` are stored in a custom app-specific nested format (with `strategy`, `settings`, and `parameters` sections). Freqtrade automatically picks up any `{StrategyName}.json` file alongside the strategy `.py` file and tries to load it as a parameter file. Freqtrade expects a flat format — just `{"param_name": value, ...}` — and fails with "Invalid parameter file provided" when it encounters the custom nested format, crashing every backtest run.

## Done looks like
- All strategy `.json` files in `user_data/strategies/` are in Freqtrade's flat format: `{"param_name": value, ...}` containing only the optimizable parameter values.
- Running a backtest for any strategy (e.g. `MultiMa`) no longer produces the "Invalid parameter file provided" error.
- Parameter values are preserved from the `"value"` field of the old `"parameters"` section.

## Out of scope
- Changing how the app reads or writes strategy parameters going forward (`.params` files are already handled separately).
- Modifying any strategy `.py` files.
- Migrating `settings` fields (minimal_roi, stoploss, etc.) — those belong in the strategy code, not the parameter file.

## Tasks
1. **Migrate strategy JSON files** — Write a one-time migration script that reads each strategy `.json` in `user_data/strategies/`, extracts the `"value"` field from each entry in the `"parameters"` section, and rewrites the file as a flat JSON `{"param_name": value, ...}`. Run it against all 24 affected files.

2. **Guard future writes** — If any code path in the app ever writes to `user_data/strategies/{strategy}.json`, ensure it writes the flat Freqtrade-compatible format. Audit the codebase for any such writes and correct them.

## Relevant files
- `user_data/strategies/MultiMa.json`
- `app/services/hyperopt_parser.py`
- `app/services/command_builder.py`
