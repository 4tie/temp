# Fix Duplicate Command Block

## What & Why
After Task #10, there are two command block elements:
- `#bt-cmd-preview` in the Configuration card — the live-updating preview (correct, keep this).
- `#bt-cmd` inside the status card (`#bt-status-card`) — the old post-run block (now redundant, shows as an empty COMMAND header).

The user sees the empty block and wants only one command shown, updating live as they change fields.

## Done looks like
- Only one command block is visible: the live preview in the Configuration card.
- It updates immediately when the user changes strategy, timeframe, timerange, pairs, or any of the four config-synced fields (wallet, max trades, stake, strategy).
- The empty "COMMAND / Copy" placeholder is gone — the preview only renders when there is a valid command to show (at least one pair selected; placeholder text if no pairs yet).
- The status card no longer contains a command block.

## Out of scope
- Hyperopt page
- Any other UI changes

## Tasks
1. **Remove `#bt-cmd` from status card** — Delete the `<div id="bt-cmd"></div>` line from the HTML template inside `#bt-status-card`, and remove the `_renderCommandBlock(cmdEl, data.meta.command)` call from `_updateStatus()` in `static/js/pages/backtesting.js`.

2. **Guard empty preview** — In `_refreshCommandPreview()`, if no pairs are selected, clear the `#bt-cmd-preview` container (set innerHTML to `''`) rather than rendering an empty block. If at least one pair is selected, render normally.

3. **Refresh preview after config sync** — In `_wireConfigSyncEvents()`, call `_refreshCommandPreview()` after a successful `patchConfig` response so the live command updates when strategy/wallet/trades/stake fields change.

## Relevant files
- `static/js/pages/backtesting.js:320-360,184-230,688-710`
