---
name: diagnostics
description: Debug static and runtime issues in the 4tie repo using logs, health checks, targeted traces, and focused inspection. Use when behavior is broken, errors appear, or recent changes need root-cause analysis.
---

# Diagnostics

Use this skill when:
- The app is broken, unstable, or inconsistent.
- Recent changes introduced unexpected errors.
- You need root-cause analysis instead of a blind patch.

Debug surfaces:
- `python run.py status` and `/healthz`.
- `python run.py logs --lines 100` and `user_data/runtime/server.log`.
- Browser-facing issues in `templates/`, `static/js/`, network calls, or route handlers.

Workflow:
1. Reproduce the issue with the smallest reliable sequence.
2. Separate startup, backend, data, and frontend symptoms.
3. Narrow the cause to one layer before fixing it.
4. Rerun the smallest proving check after the fix.
