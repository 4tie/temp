---
name: deployment
description: Prepare the 4tie app for deployment and triage runtime issues after release. Use when checking production readiness, launch blockers, runtime logs, or deployment regressions.
---

# Deployment

Use this skill when:
- The user wants a deployment-readiness check.
- A released build behaves differently than local.
- You need a concise launch checklist.

4tie release gate:
- `python run.py start --foreground` succeeds.
- `python run.py status` and `/healthz` succeed.
- Relevant Playwright flows pass.
- `user_data/runtime/server.log` has no new errors.

Workflow:
1. Confirm the exact command, host, port, and environment variables.
2. Reproduce failures locally when possible.
3. Compare logs, routes, and asset paths.
4. Classify blockers as launch-stopping, launch-risky, or follow-up.
