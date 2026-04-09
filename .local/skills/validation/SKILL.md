---
name: validation
description: Run and document repo-local validation for 4tie using health checks, Playwright, and targeted acceptance commands. Use after code changes or when the user asks to verify behavior.
---

# Validation

Use this skill when:
- Code has changed and the result needs verification.
- The user asks whether a fix actually works.
- A release or handoff needs a concise proof set.

Core checks:
- `python run.py status`
- `python run.py logs --lines 100`
- `npx playwright test tests/playwright/ui-workflow-validation.spec.js --reporter=line`
- `npx playwright test tests/playwright/ui-layout.spec.js tests/playwright/visual-regression.spec.js tests/playwright/backtesting-intelligence-rerun.spec.js --reporter=line`

Workflow:
1. Choose the smallest validation set that proves the changed behavior.
2. Confirm basic server health before browser checks.
3. Return what passed, what failed, and what remains untested.
