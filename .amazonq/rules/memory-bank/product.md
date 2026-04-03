# Product Overview — 4tie

## Project Purpose
4tie is a web-based management interface for the FreqTrade algorithmic trading framework. It provides a unified UI to run backtests, manage strategies, optimize parameters via hyperopt, and get AI-powered analysis of trading strategy performance — all without touching the command line.

## Value Proposition
- Eliminates manual FreqTrade CLI usage for common workflows
- Provides AI-assisted strategy diagnosis with multi-model pipeline analysis
- Centralizes strategy management, backtesting, and results comparison in one interface
- Supports both local (Ollama) and cloud (OpenRouter) AI providers

## Key Features

### Backtesting
- Run FreqTrade backtests from the web UI with configurable strategy, pairs, timeframe, and timerange
- View per-run results with trade details, charts, and summary metrics
- Download OHLCV market data directly from the UI
- Compare multiple backtest runs side-by-side

### Strategy Management (Strategy Lab)
- List, view, and manage FreqTrade strategy files
- Edit strategy parameters (IntParameter/DecimalParameter knobs) via JSON sidecar files
- Scan and display available strategies from user_data/strategies/

### Hyperopt
- Launch hyperopt optimization runs from the UI
- View and compare hyperopt results across runs

### AI Diagnosis
- Full chat interface with streaming responses (SSE)
- Multi-model pipeline engine: simple, analysis, debate, code, structured, tool pipelines
- Goal-directed analysis (lower drawdown, higher win rate, maximize profit, etc.)
- Deep backtest analysis with health scoring, strengths/weaknesses, parameter recommendations
- Conversation history persisted to disk (JSON files)
- Provider toggle: Ollama (local) or OpenRouter (cloud)
- Model picker per conversation
- Inject latest backtest context into chat

### Jobs Monitor
- Track active FreqTrade processes (backtest, download, hyperopt)
- View live logs from running jobs

## Target Users
- Algorithmic traders using FreqTrade who want a GUI workflow
- Quant developers iterating on strategy parameters and wanting AI feedback
- Users who want to compare strategy performance across multiple runs without manual log parsing

## Use Cases
1. Run a backtest → view results → ask AI to diagnose weaknesses → get parameter suggestions
2. Compare multiple strategy variants side-by-side to pick the best performer
3. Generate new FreqTrade strategy code via AI chat with code pipeline
4. Optimize strategy parameters via hyperopt and review results in the UI
