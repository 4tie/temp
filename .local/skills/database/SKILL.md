---
name: database
description: Inspect and reason about the 4tie app's local data stores, runtime files, and SQL-backed artifacts. Use when debugging stored state, run outputs, or repo-local databases.
---

# Database

Use this skill when:
- Stored state looks wrong or stale.
- A bug depends on files under `user_data/` or local databases.
- You need safe inspection of result bundles, presets, or SQLite data.

4tie data surfaces:
- `app/core/config.py` resolves `USER_DATA_DIR`.
- Result artifacts live under `user_data/backtest_results/` and `user_data/hyperopt_results/`.
- Repo-local databases can include `tradesv3.sqlite` and related runtime copies.

Workflow:
1. Separate configuration issues from on-disk state and query logic.
2. Prefer read-only inspection first.
3. Confirm exact file paths before any mutation.
4. Record filters, sort order, and timestamp assumptions when querying data.
