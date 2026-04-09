---
name: environment-secrets
description: Manage repo-local configuration and secret handling for 4tie. Use when working with `.env`, `USER_DATA_DIR`, API keys, ports, or runtime environment variables.
---

# Environment Secrets

Use this skill when:
- You need to inspect or change runtime configuration.
- A bug depends on `.env` values, paths, or service credentials.
- The user needs help understanding which variables matter for local runs.

4tie configuration surfaces:
- `.env` is loaded by `run.py`.
- `app/core/config.py` reads `USER_DATA_DIR`, `BACKTEST_API_HOST`, `BACKTEST_API_PORT`, and related defaults.
- Runtime logs can be redirected with `APP_LOG_FILE`.

Rules:
1. Never print secret values back unless explicitly requested.
2. Keep durable defaults in code and sensitive values out of tracked files.
3. Restart the local run loop and verify `/healthz` after configuration changes.
