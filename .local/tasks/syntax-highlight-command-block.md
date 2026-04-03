# Syntax-Highlight the Command Block

## What & Why
The command displayed in the status card is currently shown as a multi-line plain-text block with `\` continuations. The user wants it displayed as a single-line, syntax-coloured command where each token type has its own colour, making it easier to read at a glance.

## Done looks like
- The command is displayed on a **single line** (no `\` line continuations, no newlines).
- Each token is wrapped in a `<span>` with a colour class:
  - **Executable / subcommand** (`python`, `-m`, `freqtrade`, `backtesting`, `hyperopt`, `download-data`) → violet (`--color-violet`)
  - **Flags** (tokens starting with `-`, e.g. `-c`, `--timeframe`, `--export`, `--pairs`) → muted grey (`--color-muted` / `--text-secondary`)
  - **Paths** (tokens containing `/` or `user_data`) → rose/pink (`#f43f5e` or a new `--color-rose` variable)
  - **Plain values** (timeframe values like `5m`, numbers, `trades`, pair names like `ETH/USDT`) → amber (`--color-amber`)
- The Copy button still copies the full raw single-line command string (no spans, no colour markup).
- The `.cmd-block__pre` scrolls horizontally if the line is too long (no wrapping).
- The same syntax highlighting is applied in both Backtesting and Hyperopt pages.

## Out of scope
- Changing the actual command that runs (that is Task #7).
- Adding new token types beyond the four categories above.

## Tasks
1. **Token classifier + renderer** — Update `_renderCommandBlock()` in both `backtesting.js` and `hyperopt.js` to: split the flat command array into individual tokens, classify each token (executable/subcommand, flag, path, or value), and emit a `<span class="cmd-token cmd-token--<type>">` per token separated by spaces. The `pre` element should have `white-space: pre` and `overflow-x: auto`.

2. **Token colour CSS** — Add `.cmd-token--exec` (violet), `.cmd-token--flag` (muted grey), `.cmd-token--path` (rose `#f43f5e`), `.cmd-token--value` (amber) classes to `static/css/components.css`. Set `white-space: pre` on `.cmd-block__pre` and `overflow-x: auto` so the single line scrolls rather than wrapping.

## Relevant files
- `static/js/pages/backtesting.js`
- `static/js/pages/hyperopt.js`
- `static/css/components.css`
