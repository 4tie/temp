# Task: Strategy Evolution UI — Frontend

## Depends on
Task: Strategy Evolution Engine — Backend (must be merged first)

## Goal
Add an "Evolve" tab or panel to the AI Diagnosis page that lets the user trigger the evolution loop and watch it run in real time — generation by generation, with fitness comparisons, code diffs, and accept/reject controls.

---

## What the user sees

### Entry point
- In the AI Diagnosis header bar: a new **"Evolve Strategy"** button (green, only enabled when a backtest context is injected via "Inject latest backtest")
- Clicking it opens the Evolution Panel (right drawer, slides in alongside the Deep Analysis panel)

### Evolution panel — Configure tab
Before starting:
- **Goal selector**: same goals as chat (lower_drawdown, higher_profit, etc.) + "Auto (AI decides)"
- **Max generations**: spinner 1–5 (default 3)
- **Provider / Model**: reuses the same selectors from the chat header
- **Start Evolution** button (violet, full-width)

### Evolution panel — Running tab (live during evolution)
Stream of generation cards, built in real time as SSE events arrive:

```
┌─────────────────────────────────────────────────────┐
│  Generation 1 of 3                          🔄 Live │
│  ─────────────────────────────────────────────────  │
│  [●] Analyzing backtest...                          │
│  [●] AI mutating strategy code...                   │
│  [●] Running backtest on MultiMa_evo_g1...          │
│  [●] Comparing results...                           │
│                                                     │
│  Fitness: 42.1 → 57.8   (+15.7)   ✅ ACCEPTED      │
│  Changes: "Tightened stoploss from -0.345 to -0.08  │
│           and adjusted buy_ma_count default to 6"   │
│                                                     │
│  [View Code Diff]  [View Backtest]                  │
└─────────────────────────────────────────────────────┘
```

Each step shows a spinner while in progress, then a green/amber checkmark when done.
"Accepted" in green if fitness improved, "Rejected" in amber if it didn't.

Progress bar at the top of the panel: `Generation 2 / 3`.

### Evolution panel — Results tab (after completion)
Summary card at the top:
```
Best version: MultiMa_evo_g2
Fitness: 42.1 → 61.3  (+19.2)
```
All generations listed as comparison rows:
| Gen | Version | Fitness | Δ | Status |
|-----|---------|---------|---|--------|
| 1   | MultiMa_evo_g1 | 57.8 | +15.7 | Accepted |
| 2   | MultiMa_evo_g2 | 61.3 | +3.5  | Accepted |
| 3   | MultiMa_evo_g3 | 58.1 | -3.2  | Rejected |

"Accept Best Version" button (violet, bottom) — calls `POST /evolution/accept/{loop_id}/{best_gen}` then shows a toast "MultiMa_evo_g2 has been applied as MultiMa"

### Code diff view (modal)
When user clicks "View Code Diff":
- Two-column side-by-side diff (original vs new), red lines for removed, green for added
- Minimal inline diff renderer — no external library, use string comparison line by line
- Dark background, monospace font

### Fitness score display
A small horizontal bar chart per-generation (reuses health ring style from deep analysis panel):
- Bar segments: profitability, risk_control, consistency, trade_quality
- Colour: green if improved vs previous, red if worse

---

## Files to create / modify

### static/js/pages/ai-diagnosis.js
- Add `_openEvolutionPanel()` function
- Add `_startEvolution(loopId, config)` — opens SSE stream to `GET /evolution/stream/{loopId}`
- Add `_renderGenerationCard(event)` — renders one live generation card
- Add `_renderEvolutionResults(loopId)` — loads `GET /evolution/run/{loopId}` and renders results tab
- Add `_renderCodeDiff(original, mutated)` — opens modal with line-by-line diff
- Add "Evolve Strategy" button to header bar (disabled when no context injected)
- Wire "Accept Best" → `POST /evolution/accept/{loop_id}/{gen}` → toast + close panel

### static/css/pages/ai-chat.css
Add:
- `.evo-panel` — right drawer (same width as deep analysis panel, 420px)
- `.evo-step` — flex row with spinner/checkmark icon + label
- `.evo-step--pending` → grey spinner
- `.evo-step--running` → violet spinning animation
- `.evo-step--done` → green checkmark
- `.evo-step--failed` → red x
- `.evo-gen-card` — generation summary card, bordered
- `.evo-fitness-bar` — horizontal bar, violet fill
- `.evo-diff` — two-column code diff container
- `.evo-diff__line--added` → green bg
- `.evo-diff__line--removed` → red bg
- `.evo-badge--accepted` → green pill
- `.evo-badge--rejected` → amber pill

---

## API calls used
- `POST /evolution/start` — start loop, get loop_id
- `GET  /evolution/stream/{loop_id}` — SSE stream progress
- `GET  /evolution/run/{loop_id}` — full results after done
- `GET  /evolution/versions/{strategy}` — version list
- `POST /evolution/accept/{loop_id}/{generation}` — accept best
- `GET  /runs/{run_id}` (existing) — load backtest for "View Backtest" link

---

## Colour constraints (hard — no blue)
- Violet `#8b5cf6`: Start button, fitness bars, active steps
- Green `#22c55e`: accepted badge, diff added lines, checkmarks
- Amber `#f59e0b`: rejected badge, diff header
- Red `#ef4444`: diff removed lines, failed steps

---

## Acceptance criteria
- "Evolve Strategy" button appears in AI Diagnosis header when backtest context is injected
- Clicking it and pressing Start renders generation cards in real time as SSE events arrive
- Code diff modal shows clean before/after comparison
- "Accept Best Version" applies the winning version and shows a toast
