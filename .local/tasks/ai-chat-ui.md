# Task: AI Chat System UI

## Depends on
Task: AI Backend Foundation (must be merged first — endpoints must exist)

## Goal
Replace the "AI Diagnosis coming soon" placeholder with a full, dark-themed AI chat system that:
- Lets the user pick between Ollama (local) and OpenRouter (free models)
- Streams AI responses with live typing
- Persists conversation history
- Auto-injects backtest results as context
- Shows which pipeline type was chosen (simple / analysis / debate / code)
- Includes a goal selector for strategy analysis (lower_drawdown, higher_profit, etc.)

## Files to create / modify

### JavaScript
- `static/js/pages/ai-diagnosis.js` — full rewrite; exposes `window.AIDiagPage`; sections:
  - **Sidebar** — conversation list (loaded via `GET /ai/conversations`); "New chat" button; each item shows strategy name + first message preview + timestamp; delete button per row
  - **Header bar** — provider toggle (`Ollama | OpenRouter`); model select dropdown (loaded from `GET /ai/providers`); goal select dropdown (lower_drawdown, higher_win_rate, higher_profit, more_trades, cut_losers, lower_risk, scalping, swing_trading, compound_growth, or "Auto")
  - **Context injection bar** — "Inject latest backtest" button; shows the injected run's strategy + timeframe badge when active; "Clear context" link
  - **Message thread** — role-labelled bubbles (user / assistant); assistant bubble header shows pipeline badge (colour-coded: simple=grey, analysis=violet, debate=amber, code=green) + model name + duration; markdown rendered via a minimal renderer (bold, code blocks, headers, lists — no external library needed, just regex transforms); code blocks use `.cmd-block` style; streaming delta chunks appended in real-time
  - **Input area** — auto-resize textarea; file upload icon (accepts `.json`); send button; "Analysing…" spinner during streaming; Escape clears input
  - **Deep Analysis panel** — triggered by "Deep Analyse" button when a `context_run_id` is set; calls `POST /ai/analyze/{run_id}`; shows health score ring, strengths/weaknesses list, parameter recommendations, and the AI narrative sections (summary, what's working, what's not, risk, next steps)

### CSS
- `static/css/pages/ai-chat.css` — new file; imported from base.css or injected by the JS module:
  - `.ai-layout` — two-column: 260px sidebar + flex main
  - `.ai-sidebar` — near-black bg, scrollable conversation list
  - `.ai-conv-item` — hover highlight violet; active state violet-tinted bg; delete button appears on hover
  - `.ai-message--user` — right-aligned, violet bg bubble
  - `.ai-message--assistant` — left-aligned, surface-2 bg
  - `.ai-pipeline-badge` — small pill: `simple`=grey, `analysis`=violet, `debate`=amber, `code`=green
  - `.ai-provider-toggle` — pill toggle group, active=violet
  - `.ai-goal-select` — styled `<select>` matching existing `.form-select`
  - `.ai-input-bar` — sticky bottom, dark bg, rounded textarea, send button
  - `.ai-context-bar` — slim bar between header and thread showing active context
  - `.ai-health-ring` — SVG circle ring for health score (stroke-dasharray animation)
  - `.ai-deep-panel` — right drawer that slides in; close button; dark scrollable content

### HTML template
- `templates/layouts/base.html` — add `ai-chat.css` to `<head>` link tags (or inject from JS)

## API calls used
- `GET /ai/providers` → populate provider toggle + model dropdown
- `POST /ai/chat` (SSE stream) → send message, receive status + delta chunks
- `GET /ai/conversations` → load sidebar list
- `GET /ai/conversations/{id}` → load full history when switching conversations
- `DELETE /ai/conversations/{id}` → delete from sidebar
- `POST /ai/analyze/{run_id}` → deep analysis panel data
- `GET /api/runs` (existing) → "Inject latest backtest" picks the most recent completed run

## UX details
- When OPENROUTER_API_KEY is missing: provider shows "OpenRouter (no key)" in orange; clicking it shows an inline message "Set OPENROUTER_API_KEY in Secrets to enable"
- When Ollama is not running: provider shows "Ollama (offline)" in grey; disabled
- Goal selector is hidden unless provider/model is available
- Streaming: send button changes to stop icon; clicking stops the EventSource; partial message is preserved
- Mobile: sidebar collapses to a hamburger drawer below 640px

## Colour palette (hard constraint — no blue)
- Violet `#8b5cf6` for primary actions, user bubbles, active states
- Green `#22c55e` for code pipeline badge, success
- Amber `#f59e0b` for debate pipeline badge, warnings
- Red `#ef4444` for errors, delete
- Grey `#6b7280` for simple pipeline badge, muted text

## Done when
- AI Diagnosis page renders the two-column layout (no "coming soon" placeholder)
- Typing a message and sending it shows a streaming response
- Provider/model dropdowns populate correctly
- Conversation list loads and clicking an item restores the thread
- "Inject latest backtest" button populates context and shows the badge
