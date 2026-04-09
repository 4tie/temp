---
name: workflows
description: Manage the 4tie local run loop and supporting validation commands. Use when starting, stopping, restarting, or observing the app and its QA workflows.
---

# Workflows

Use this skill when:
- The app needs to be started, restarted, or checked after a change.
- A contributor needs the canonical local run commands.
- You need to watch logs or keep a persistent test loop running.

4tie run loop:
- Start with `python run.py start --foreground`.
- Check health with `python run.py status` and `/healthz`.
- Read recent logs with `python run.py logs --lines 100`.
- Use the host tool's persistent terminal or process support when available.

Workflow:
1. Keep one clear source of truth for the running server.
2. Restart after backend, template, or environment changes that are not hot-reloaded safely.
3. Confirm startup, health, and relevant logs before handing the app back.
