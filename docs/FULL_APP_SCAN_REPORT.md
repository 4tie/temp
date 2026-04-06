# Full App Scan Report

## Current status (real app state)
- Report date: 2026-04-07 (Asia/Riyadh)
- Repo: `t:\SameGrossNetframework\SameGrossNetframework`
- Commit: `092b3b9`

## Latest validated results
Source of truth:
- `docs/qa/ui-workflow-summary-latest.json`
- `docs/qa/ui-workflow-validation-pass-latest.md`
- `docs/qa/ui-workflow-validation-issues-latest.md`

Latest counts:
- Inventory actions: 78
- Validated actions: 78
- PASS: 5
- BLOCKED: 19
- MISSING: 9
- FAIL: 45

Interpretation:
- The workflow scanner is currently strict and heuristic-based.
- `BLOCKED` mostly means the control exists but required preconditions were not met in test setup.
- `MISSING` means no observable effect was detected by the scanner for that control.
- `FAIL` means runtime interaction failed during automated click-to-effect validation.

## Regression suites status
Latest regression run in the workflow pipeline:
- Playwright regression specs passed:
  - `tests/playwright/ui-layout.spec.js`
  - `tests/playwright/visual-regression.spec.js`
  - `tests/playwright/backtesting-intelligence-rerun.spec.js`

Result:
- 51 passed (cross-browser run)

## What is reliable vs pending
Reliable now:
- Layout integrity checks
- Visual regression baselines
- Backtesting intelligence rerun flow tests
- Full workflow inventory/report generation pipeline

Pending triage:
- High FAIL/MISSING volume in exhaustive button workflow scan
- AI Diagnosis and some dynamic controls require stronger precondition setup in validation harness
- Some selectors in reports are generic nth-of-type paths and should be hardened to stable IDs/data attributes

## Commands to reproduce current status
```bash
node scripts/build_ui_workflow_inventory.js
npx playwright test tests/playwright/ui-workflow-validation.spec.js --reporter=line
npx playwright test tests/playwright/ui-layout.spec.js tests/playwright/visual-regression.spec.js tests/playwright/backtesting-intelligence-rerun.spec.js --reporter=line
node scripts/generate_ui_workflow_reports.js
```

Or run all in one:
```bash
npm run validate:ui-workflows
```

## Notes
- The orchestration command exits non-zero if FAIL/MISSING remains.
- This report intentionally reflects current measured status, not projected/target status.
