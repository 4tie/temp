# Advanced AI Engine — Full Architecture

## What & Why
Upgrade the existing AI subsystem from a functional prototype into a production-grade, multi-model reasoning engine. The current code has the right skeleton (orchestrator, classifier, debate mode, dual providers) but lacks robustness, goal-awareness, auto-context, persistent memory, and visible reasoning traces. This task completes all eight pillars the user described.

## Done looks like
- Every AI request goes through classifier → orchestrator → one or more models → composed answer. The user can see each step in the UI (which model was used, which pipeline ran, how long each step took).
- Debate pipeline is fully wired: two analyst models produce competing arguments, a judge model synthesizes a final verdict. Result clearly shows the disagreement and resolution.
- Provider layer automatically rotates API keys (if multiple are configured), retries failed calls with exponential backoff, and falls back from OpenRouter to Ollama when all cloud calls fail.
- Users can set a goal (maximize profit / reduce drawdown / improve win rate / balanced) in the UI. Every AI analysis and chat response is framed around that goal.
- Backtest results, active strategy config, and relevant settings are automatically injected into AI context — the user does not need to paste them manually.
- Conversation threads are persisted to disk under `user_data/ai_threads/`. Users can resume any prior thread; context snapshots are saved at the start of each session.
- A "thinking trace" panel in the chat UI shows the real-time pipeline steps: classifier decision, pipeline selected, models chosen, per-step outputs, and total time.

## Out of scope
- Paid/premium OpenRouter models (free tier only)
- Training or fine-tuning any model
- Multi-user thread isolation (single-user app)
- Tool-calling with external APIs beyond what already exists in the project

## Tasks

1. **Fault-tolerant provider layer** — Add API key rotation (read multiple keys from env), per-call retry with exponential backoff (3 attempts), and an automatic fallback chain: OpenRouter → Ollama. Wrap `provider_dispatch.py` and both clients so all callers get this transparently.

2. **Goal-driven context builder** — Add a `GoalType` enum (maximize_profit, reduce_drawdown, improve_win_rate, balanced). Create a context-builder module that accepts a goal and auto-injects relevant backtest metrics, strategy config JSON, and user settings into the system prompt. Wire this into every pipeline run.

3. **Persistent thread / memory system** — Implement a thread store under `user_data/ai_threads/` (one JSON file per thread). Each thread stores: thread ID, goal, creation timestamp, ordered message history, and a context snapshot taken at thread start. Expose CRUD endpoints: list threads, get thread, delete thread, append message.

4. **Complete debate pipeline** — Ensure the debate pipeline is fully end-to-end: spawn two analyst calls in parallel with opposing framings, collect both arguments, then run a judge call that explicitly references both sides and delivers a structured verdict (agreement points, disagreement points, final recommendation). Stream the judge step to the UI.

5. **Thinking trace — backend** — Extend `PipelineResult` and the streaming SSE endpoint to emit structured step events: `classifier_decision`, `pipeline_selected`, `step_start`, `step_complete`, `final`. Each event includes model ID, role, duration, and a short output preview.

6. **Thinking trace + goal selector — frontend** — Add a goal selector (dropdown or segmented control) to the chat UI. Add a collapsible "Thinking" panel below each AI response that renders the step events in real time as the pipeline runs. Wire thread list into the conversation history sidebar so users can switch and resume threads.

## Relevant files
- `app/ai/ai_orchestrator.py`
- `app/ai/ai_classifier.py`
- `app/ai/provider_dispatch.py`
- `app/ai/openrouter_client.py`
- `app/ai/ollama_client.py`
- `app/ai/ai_registry.py`
- `app/ai/deep_analysis.py`
- `app/ai/memory/`
- `app/ai/pipelines/`
- `app/ai/prompts/`
- `app/ai/tools/`
