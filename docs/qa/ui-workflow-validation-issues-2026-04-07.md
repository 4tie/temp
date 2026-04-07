# UI Workflow Validation - Issues Report

- Date: 2026-04-07
- Commit: `4972986`
- PASS: 65 | BLOCKED: 13 | MISSING: 1 | FAIL: 0

## Summary
14 non-pass actions detected requiring remediation.

## Issues
| Severity | Page | Control | Selector | Status | Root Cause (probable) | Fix Guidance |
|---|---|---|---|---|---|---|
| low | ai-diagnosis | Open Deep Analysis | `.page-view.active div:nth-of-type(2) > aside:nth-of-type(1) > section:nth-of-type(1) > div:nth-of-type(2) > button:nth-of-type(1)` | BLOCKED | precondition gating | Ensure test preconditions and seed data make control actionable before validation. |
| low | ai-diagnosis | Open Evolution | `.page-view.active div:nth-of-type(2) > aside:nth-of-type(1) > section:nth-of-type(1) > div:nth-of-type(2) > button:nth-of-type(2)` | BLOCKED | precondition gating | Ensure test preconditions and seed data make control actionable before validation. |
| low | ai-diagnosis | Clear Context | `.page-view.active div:nth-of-type(2) > aside:nth-of-type(1) > section:nth-of-type(1) > div:nth-of-type(2) > button:nth-of-type(3)` | BLOCKED | precondition gating | Ensure test preconditions and seed data make control actionable before validation. |
| low | ai-diagnosis | New Conversation | `.page-view.active div:nth-of-type(2) > section:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(2) > button:nth-of-type(2)` | BLOCKED | precondition gating | Ensure test preconditions and seed data make control actionable before validation. |
| low | ai-diagnosis | (unlabeled control) | `#ai-hamburger` | BLOCKED | precondition gating | Ensure test preconditions and seed data make control actionable before validation. |
| low | ai-diagnosis | Inject latest backtest | `#ai-inject-btn2` | BLOCKED | precondition gating | Ensure test preconditions and seed data make control actionable before validation. |
| low | ai-diagnosis | Start Evolution | `#evo-start-btn` | BLOCKED | precondition gating | Ensure test preconditions and seed data make control actionable before validation. |
| low | ai-diagnosis | CONFIGURE | `#evo-tab-config` | BLOCKED | precondition gating | Ensure test preconditions and seed data make control actionable before validation. |
| medium | ai-diagnosis | (unlabeled control) | `#evo-diff-close` | MISSING | no observable workflow binding | Bind control to explicit handler and add observable effect (request/state/nav/feedback) with tests. |
| low | dashboard | (no controls found) | `(none)` | BLOCKED | precondition gating | Ensure test preconditions and seed data make control actionable before validation. |
| low | hyperopt | Apply Params | `#ho-apply-btn` | BLOCKED | precondition gating | Ensure test preconditions and seed data make control actionable before validation. |
| low | hyperopt | Stop | `#ho-stop-btn` | BLOCKED | precondition gating | Ensure test preconditions and seed data make control actionable before validation. |
| low | settings | Remove | `.page-view.active div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(2) > form:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(1) > button:nth-of-type(3)` | BLOCKED | precondition gating | Ensure test preconditions and seed data make control actionable before validation. |
| low | strategy-lab | (no controls found) | `(none)` | BLOCKED | precondition gating | Ensure test preconditions and seed data make control actionable before validation. |

## Missing Function / Workflow
- ai-diagnosis: `#evo-diff-close` ((unlabeled control)) -> no observable workflow.