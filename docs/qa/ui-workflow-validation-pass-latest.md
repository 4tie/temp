# UI Workflow Validation - Pass Report

- Date: 2026-04-07
- Commit: `068618b`
- Inventory actions: 78
- Validated actions: 79
- PASS: 65 | BLOCKED: 13 | MISSING: 1 | FAIL: 0

## Procedure
1. `node scripts/build_ui_workflow_inventory.js`
2. `npx playwright test tests/playwright/ui-workflow-validation.spec.js --reporter=line`
3. `node scripts/generate_ui_workflow_reports.js`

## Passing Action Matrix
| Page | Control | Selector | Browsers | Evidence | Confirmation |
|---|---|---|---|---|---|
| ai-diagnosis | Focus Composer | `.page-view.active div:nth-of-type(2) > section:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(2) > button:nth-of-type(1)` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| ai-diagnosis | Inject Latest Backtest | `.page-view.active div:nth-of-type(2) > section:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(2) > button:nth-of-type(3)` | chromium, firefox, webkit | GET /runs<br>GET /strategies/MomentumPulse/source | trigger-to-end completed |
| ai-diagnosis | Ollama | `#ai-btn-ollama` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| ai-diagnosis | OpenRouter | `#ai-btn-openrouter` | chromium, firefox, webkit | GET /healthz | trigger-to-end completed |
| ai-diagnosis | clear | `#ai-context-clear` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| ai-diagnosis | Show conversations | `#ai-conv-toggle` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| ai-diagnosis | Deep Analyse | `#ai-deep-analyse-btn` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| ai-diagnosis | (unlabeled control) | `#ai-deep-panel-close` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| ai-diagnosis | Evolve Strategy | `#ai-evolve-btn` | chromium, firefox, webkit | GET /healthz | trigger-to-end completed |
| ai-diagnosis | Inject latest backtest | `#ai-inject-btn` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| ai-diagnosis | Inject latest backtest | `#ai-inject-btn3` | chromium, firefox, webkit | GET /runs<br>GET /strategies/MomentumPulse/source | trigger-to-end completed |
| ai-diagnosis | Start Loop | `#ai-loop-toggle` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| ai-diagnosis | New conversation | `#ai-new-chat` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| ai-diagnosis | Send | `#ai-send-btn` | chromium, firefox, webkit | POST /ai/chat<br>GET /healthz | trigger-to-end completed |
| ai-diagnosis | (unlabeled control) | `#ai-stop-btn` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| ai-diagnosis | (unlabeled control) | `#evo-panel-close` | chromium, firefox, webkit | GET /healthz | trigger-to-end completed |
| ai-diagnosis | RESULTS | `#evo-tab-results` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| ai-diagnosis | RUNNING | `#evo-tab-running` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| backtesting | ♥ | `.page-view.active div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(2) > form:nth-of-type(1) > div:nth-of-type(3) > div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(2) > button:nth-of-type(1)` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| backtesting | ♥ | `.page-view.active div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(2) > form:nth-of-type(1) > div:nth-of-type(3) > div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(3) > button:nth-of-type(1)` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| backtesting | ♥ | `.page-view.active div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(2) > form:nth-of-type(1) > div:nth-of-type(3) > div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(5) > button:nth-of-type(1)` | chromium, firefox, webkit | GET /healthz | trigger-to-end completed |
| backtesting | ♥ | `.page-view.active div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(2) > form:nth-of-type(1) > div:nth-of-type(3) > div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(7) > button:nth-of-type(1)` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| backtesting | ♥ | `.page-view.active div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(2) > form:nth-of-type(1) > div:nth-of-type(3) > div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(8) > button:nth-of-type(1)` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| backtesting | ♥ | `.page-view.active div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(2) > form:nth-of-type(1) > div:nth-of-type(3) > div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(9) > button:nth-of-type(1)` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| backtesting | Improve & Run | `.page-view.active div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(2) > section:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(2) > button:nth-of-type(1)` | chromium, firefox, webkit | GET /pairs<br>POST /data-coverage<br>POST /run | trigger-to-end completed |
| backtesting | Open Full Explorer | `.page-view.active div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(2) > section:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(2) > button:nth-of-type(2)` | chromium, firefox, webkit | GET /runs/bt_run_completed_1<br>GET /runs/bt_run_completed_1/raw | trigger-to-end completed |
| backtesting | Save and Run | `.page-view.active div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(3) > div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(1) > button:nth-of-type(1)` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| backtesting | Run Again | `.page-view.active div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(3) > div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(1) > button:nth-of-type(2)` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| backtesting | Save to Strategy | `.page-view.active div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(3) > div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(1) > button:nth-of-type(3)` | chromium, firefox, webkit | GET /healthz | trigger-to-end completed |
| backtesting | Reset | `.page-view.active div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(3) > div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(1) > button:nth-of-type(4)` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| backtesting | Delete Run | `#bt-delete-btn` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| backtesting | Download Data | `#bt-dl-form-btn` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| backtesting | All | `#bt-pairs-all` | chromium, firefox, webkit | GET /healthz | trigger-to-end completed |
| backtesting | ★ Favs | `#bt-pairs-favs` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| backtesting | Clear | `#bt-pairs-none` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| backtesting | Run Backtest | `#bt-run-btn` | chromium, firefox, webkit | GET /healthz | trigger-to-end completed |
| backtesting | Stop | `#bt-stop-btn` | chromium, firefox, webkit | GET /healthz | trigger-to-end completed |
| hyperopt | ♥ | `.page-view.active div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(2) > form:nth-of-type(1) > div:nth-of-type(3) > div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(2) > button:nth-of-type(1)` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| hyperopt | ♥ | `.page-view.active div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(2) > form:nth-of-type(1) > div:nth-of-type(3) > div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(3) > button:nth-of-type(1)` | chromium, firefox, webkit | GET /healthz | trigger-to-end completed |
| hyperopt | ♥ | `.page-view.active div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(2) > form:nth-of-type(1) > div:nth-of-type(3) > div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(5) > button:nth-of-type(1)` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| hyperopt | ♥ | `.page-view.active div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(2) > form:nth-of-type(1) > div:nth-of-type(3) > div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(7) > button:nth-of-type(1)` | chromium, firefox, webkit | GET /healthz | trigger-to-end completed |
| hyperopt | Download Data | `#ho-dl-form-btn` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| hyperopt | All | `#ho-pairs-all` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| hyperopt | ★ Favs | `#ho-pairs-favs` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| hyperopt | Clear | `#ho-pairs-none` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| hyperopt | Start Hyperopt | `#ho-run-btn` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| jobs | Refresh | `#jobs-refresh-btn` | chromium, firefox, webkit | GET /runs<br>GET /hyperopt/runs<br>GET /activity | trigger-to-end completed |
| results | View | `.page-view.active div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(2) > table:nth-of-type(1) > tbody:nth-of-type(1) > tr:nth-of-type(1) > td:nth-of-type(4) > button:nth-of-type(1)` | chromium, firefox, webkit | GET /runs/bt_run_completed_1<br>GET /runs/bt_run_completed_1/raw | trigger-to-end completed |
| results | Apply | `.page-view.active div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(2) > table:nth-of-type(1) > tbody:nth-of-type(1) > tr:nth-of-type(1) > td:nth-of-type(4) > button:nth-of-type(2)` | chromium, firefox, webkit | POST /runs/bt_run_completed_1/apply-config | trigger-to-end completed |
| settings | Show | `.page-view.active div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(2) > form:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(1) > button:nth-of-type(1)` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| settings | Test | `.page-view.active div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(2) > form:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(1) > button:nth-of-type(2)` | chromium, firefox, webkit | POST /settings/test-openrouter-key | trigger-to-end completed |
| settings | Ocean Teal and cyan ACTIVE | `.page-view.active div:nth-of-type(2) > div:nth-of-type(3) > div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(1) > button:nth-of-type(1)` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| settings | Midnight Dark blue and slate | `.page-view.active div:nth-of-type(2) > div:nth-of-type(3) > div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(1) > button:nth-of-type(10)` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| settings | Ember Amber and coral | `.page-view.active div:nth-of-type(2) > div:nth-of-type(3) > div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(1) > button:nth-of-type(2)` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| settings | Aurora Green and mint | `.page-view.active div:nth-of-type(2) > div:nth-of-type(3) > div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(1) > button:nth-of-type(3)` | chromium, firefox, webkit | GET /healthz | trigger-to-end completed |
| settings | Cobalt Blue and ice | `.page-view.active div:nth-of-type(2) > div:nth-of-type(3) > div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(1) > button:nth-of-type(4)` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| settings | Ruby Rose and magenta | `.page-view.active div:nth-of-type(2) > div:nth-of-type(3) > div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(1) > button:nth-of-type(5)` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| settings | Amethyst Purple and lavender | `.page-view.active div:nth-of-type(2) > div:nth-of-type(3) > div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(1) > button:nth-of-type(6)` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| settings | Sunset Orange and peach | `.page-view.active div:nth-of-type(2) > div:nth-of-type(3) > div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(1) > button:nth-of-type(7)` | chromium, firefox, webkit | GET /healthz | trigger-to-end completed |
| settings | Forest Deep green and moss | `.page-view.active div:nth-of-type(2) > div:nth-of-type(3) > div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(1) > button:nth-of-type(8)` | chromium, firefox, webkit | GET /healthz | trigger-to-end completed |
| settings | Sakura Pink and cherry blossom | `.page-view.active div:nth-of-type(2) > div:nth-of-type(3) > div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(1) > button:nth-of-type(9)` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| settings | Save All Settings | `#master-save-btn` | chromium, firefox, webkit | POST /settings<br>GET /healthz | trigger-to-end completed |
| settings | + Add key | `#s-or-add` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| settings | Clear | `#s-or-clear` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |
| settings | Save Current as Preset | `#s-save-preset-btn` | chromium, firefox, webkit | State/UI effect | trigger-to-end completed |