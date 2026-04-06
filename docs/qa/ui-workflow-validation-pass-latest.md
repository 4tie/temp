# UI Workflow Validation - Pass Report

- Date: 2026-04-07
- Commit: `092b3b9`
- Inventory actions: 78
- Validated actions: 78
- PASS: 5 | BLOCKED: 19 | MISSING: 9 | FAIL: 45

## Procedure
1. `node scripts/build_ui_workflow_inventory.js`
2. `npx playwright test tests/playwright/ui-workflow-validation.spec.js --reporter=line`
3. `node scripts/generate_ui_workflow_reports.js`

## Passing Action Matrix
| Page | Control | Selector | Browsers | Evidence | Confirmation |
|---|---|---|---|---|---|
| backtesting | ♥ | `.page-view.active div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(2) > form:nth-of-type(1) > div:nth-of-type(3) > div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(2) > button:nth-of-type(1)` | chromium, firefox, webkit | GET /healthz | trigger-to-end completed |
| backtesting | ♥ | `.page-view.active div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(2) > form:nth-of-type(1) > div:nth-of-type(3) > div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(3) > button:nth-of-type(1)` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| backtesting | ♥ | `.page-view.active div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(2) > form:nth-of-type(1) > div:nth-of-type(3) > div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(7) > button:nth-of-type(1)` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| backtesting | ♥ | `.page-view.active div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(2) > form:nth-of-type(1) > div:nth-of-type(3) > div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(9) > button:nth-of-type(1)` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| backtesting | Delete Run | `#bt-delete-btn` | chromium, firefox, webkit | GET /healthz | trigger-to-end completed |