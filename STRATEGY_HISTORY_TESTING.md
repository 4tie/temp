# Strategy History & Restoration System - Testing Guide

## Implementation Summary

A complete strategy history and restoration system has been added on top of the existing staging/version infrastructure. The system automatically creates snapshots before risky strategy writes, maintains a dedicated history store, and provides both API and UI access to restore previous versions.

## Files Created

### Core Services
- **`app/services/strategies/strategy_restore_service.py`** - Main service for history management
  - Snapshot creation, loading, restoring
  - Result enrichment with backtest data
  - Comparison utilities

### Modified Files
- `app/core/config.py` - Added `STRATEGY_HISTORY_DIR`
- `app/routers/strategies.py` - Added history endpoints
- `app/services/strategies/__init__.py` - Exported new functions
- `app/services/strategies/strategy_source_service.py` - Auto-snapshot on source save
- `app/services/strategies/strategy_sidecar_service.py` - Auto-snapshot on param save
- `app/services/strategies/strategy_snapshot_service.py` - Auto-snapshot on version promote
- `app/services/ai_chat/apply_code_service.py` - Auto-snapshot on direct apply
- `app/services/runs/backtest_run_service.py` - Added `snapshot_id` field to meta
- `templates/pages/strategy-lab/index.html` - Added History tab
- `static/js/pages/strategy-lab.js` - History UI logic

## Backend API Endpoints

### GET /api/strategies/{strategy}/history
List all snapshots for a strategy, enriched with result summaries.

**Response:**
```json
{
  "strategy": "MultiMa",
  "snapshots": [
    {
      "snapshot_id": "uuid-...",
      "strategy_name": "MultiMa",
      "created_at": "2026-04-10T14:23:45.123456",
      "reason": "save_strategy_source",
      "actor": "user",
      "linked_run_id": "20260410_142300_abc123",
      "source_bytes": 2048,
      "sidecar_bytes": 512,
      "source_hash": "sha256...",
      "sidecar_hash": "sha256...",
      "result_summary": {
        "run_id": "20260410_142300_abc123",
        "starting_balance": 1000,
        "final_balance": 1250,
        "profit_percent": 25.0,
        "total_trades": 15,
        "win_rate": 66.7,
        "max_drawdown": 5.2,
        "timeframe": "1h",
        "pairs": ["BTC/USDT", "ETH/USDT"],
        "exchange": "binance"
      }
    }
  ]
}
```

### GET /api/strategies/{strategy}/history/{snapshot_id}
Load a specific snapshot's data.

**Response:**
```json
{
  "snapshot_id": "uuid-...",
  "strategy_name": "MultiMa",
  "source": "# Strategy source code...",
  "sidecar": {
    "strategy_name": "MultiMa",
    "params": {
      "buy": { "buy_ma_count": 4, ... },
      "sell": { "sell_ma_count": 12, ... }
    }
  },
  "meta": { /* metadata object */ },
  "snapshot_dir": "/path/to/snapshot"
}
```

### POST /api/strategies/{strategy}/history/snapshot
Manually create a snapshot.

**Request:**
```json
{
  "reason": "manual_backup",
  "actor": "user",
  "linked_run_id": null,
  "metadata": { "custom_field": "value" }
}
```

**Response:**
```json
{
  "snapshot_id": "uuid-...",
  "strategy_name": "MultiMa",
  "snapshot_dir": "/path/to/history/MultiMa/uuid-.../",
  "source_path": "/path/to/.../source.py",
  "sidecar_path": "/path/to/.../sidecar.json",
  "meta_path": "/path/to/.../meta.json",
  "meta": { /* full metadata */ }
}
```

### POST /api/strategies/{strategy}/history/{snapshot_id}/restore
Restore a snapshot to become the live strategy.

**Response:**
```json
{
  "ok": true,
  "strategy_name": "MultiMa",
  "snapshot_id": "uuid-...",
  "source_path": "/path/to/MultiMa.py",
  "sidecar_path": "/path/to/MultiMa.json",
  "source_bytes": 2048,
  "sidecar_bytes": 512
}
```

### GET /api/strategies/{strategy}/history/{snapshot_id}/compare
Compare snapshot to current live state.

**Response:**
```json
{
  "strategy_name": "MultiMa",
  "snapshot_id": "uuid-...",
  "source_diff": {
    "has_changes": true,
    "snapshot_lines": 156,
    "current_lines": 159,
    "snapshot_bytes": 2048,
    "current_bytes": 2101
  },
  "sidecar_diff": {
    "has_changes": false,
    "snapshot_keys": ["strategy_name", "params"],
    "current_keys": ["strategy_name", "params"]
  },
  "snapshot_meta": { /* metadata */ }
}
```

## Frontend UI Components

### Strategy Lab History Tab
Located in Strategy Lab page, accessible from the "History" tab.

**Features:**
1. **Snapshot Cards** - Display each snapshot with:
   - Timestamp in local timezone
   - Actor badge (user/ai/system)
   - Reason badge (operation type)
   - Source size in bytes
   - Result summary metrics (if linked to backtest):
     - Profit percentage
     - Number of trades & win rate
     - Other performance indicators

2. **Actions:**
   - **Restore** - Restore snapshot (with confirmation dialog)
     - Auto-creates pre-restore snapshot for safety
   - **Compare** - Show diff between snapshot and current
     - Source line count diff
     - Sidecar changes indicator

## Testing Scenarios

### Scenario 1: Auto-Snapshot on Source Save
1. Open Strategy Lab, select any strategy
2. Modify the source code in the editor
3. Click "Save" button
4. Switch to "History" tab
5. Verify a new snapshot appears with:
   - Recent timestamp
   - Reason: "save_strategy_source"
   - Actor: "user" or "system" (depending on who saved)

### Scenario 2: Auto-Snapshot on Parameter Save
1. In Strategy Lab, modify parameter values in the inspector
2. Click "Save" button for parameters
3. Switch to History tab
4. Verify new snapshot with reason: "save_strategy_current_values"

### Scenario 3: Auto-Snapshot on Version Promotion
1. Create a staged version via "Stage" button
2. Accept the staged version
3. Check History tab
4. Verify snapshot with reason: "promote_staged_strategy_version"

### Scenario 4: Manual Snapshot Creation
```bash
curl -X POST http://localhost:8000/api/strategies/MultiMa/history/snapshot \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "before_backtest_experiment",
    "actor": "user",
    "linked_run_id": null,
    "metadata": {"experiment": "test_params_v2"}
  }'
```

### Scenario 5: Restore Workflow
1. Navigate to History tab
2. Click "Restore" on any snapshot
3. Confirm the restore action
4. Verify:
   - Dialog confirms current state will be auto-saved
   - Strategy source/params update to snapshot values
   - New pre-restore snapshot appears in history
   - Source editor shows restored code

### Scenario 6: Snapshot Comparison
1. Click "Compare" on any snapshot
2. Verify dialog shows:
   - Whether source changed (line count diff)
   - Whether sidecar changed
   - Snapshot vs current statistics

### Scenario 7: Backtest Result Linking
1. Run a backtest on a strategy
2. Create manual snapshot linking to the run:
```bash
curl -X POST http://localhost:8000/api/strategies/MultiMa/history/snapshot \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "backtest_result_snapshot",
    "actor": "user",
    "linked_run_id": "20260410_142300_abc123"
  }'
```
3. Navigate to History
4. Verify snapshot shows result summary:
   - Profit %, trades, win rate
   - Timeframe, pairs
   - Starting/final balance

## Storage Layout Verification

Check the directory structure:
```bash
ls -la user_data/strategy_history/
# Should show: MultiMa/
#              SomethingElse/

ls -la user_data/strategy_history/MultiMa/
# Should show multiple snapshot UUIDs as folders

ls -la "user_data/strategy_history/MultiMa/uuid-../
# Should contain:
#   - source.py        (strategy code at time of snapshot)
#   - sidecar.json     (parameter values at time of snapshot)
#   - meta.json        (metadata with timestamps, hashes, etc.)
```

## Metadata Inspection

View snapshot metadata:
```bash
cat user_data/strategy_history/MultiMa/uuid-../meta.json | python -m json.tool
```

Expected structure:
```json
{
  "snapshot_id": "uuid-value",
  "strategy_name": "MultiMa",
  "created_at": "2026-04-10T14:23:45.123456",
  "reason": "save_strategy_source",
  "actor": "user",
  "linked_run_id": null,
  "source_path": "/abs/path/user_data/strategies/MultiMa.py",
  "sidecar_path": "/abs/path/user_data/strategies/MultiMa.json",
  "source_hash": "sha256-...",
  "sidecar_hash": "sha256-...",
  "source_bytes": 2048,
  "sidecar_bytes": 512,
  "base_version_name": null
}
```

## Integration Points

### How It Integrates with Existing Flows

1. **Staged Versions** (existing `_evo_gN.py` system)
   - Snapshots are independent
   - Staging does NOT trigger snapshots (only live changes do)
   - Promoting a staged version DOES trigger a pre-promotion snapshot
   - Both systems can coexist

2. **Evolution System** (AI-driven mutations)
   - Evolution creates `_evo_gN.py` versions (existing)
   - When evolution promotes, snapshot is created
   - Evolution and history are separate concerns

3. **AI Code Apply** (apply_code_service.py)
   - Direct apply to live strategy → snapshot created
   - Staged apply (no direct_apply) → snapshot NOT created
   - Pre-apply snapshot preserves old state

4. **Backtest Results**
   - Run metadata now includes optional `snapshot_id` field
   - Caller can link snapshot to backtest at execution time
   - Snapshots are enriched with result summary if linked

## Limitations & Future Work

### Current Limitations
1. Backtest linking is not automatic - requires caller to set `linked_run_id` in extra_meta
2. No automatic cleanup of old snapshots (manual management required)
3. Comparison view is text-based summary, not full diff viewer
4. No batch operations (delete multiple, export, etc.)

### Recommended Enhancements
1. Auto-link snapshot_id when backtest starts (modify runner.py)
2. Implement retention policy (e.g., keep last 50 per strategy)
3. Add visual diff view with side-by-side editor
4. Add snapshot search/filtering by metadata
5. Export/import snapshots for sharing strategies
6. Tag snapshots manually for organization
7. Add snapshot description/notes field

## Validation Checklist

- [ ] All Python files compile without errors
- [ ] `strategy_restore_service.py` imports correctly
- [ ] Router endpoints are accessible (check logs for 404s)
- [ ] History directory is created at startup
- [ ] Snapshots are created before risky writes
- [ ] Snapshot files (source.py, sidecar.json, meta.json) exist
- [ ] History tab appears in Strategy Lab UI
- [ ] Restore functionality works end-to-end
- [ ] Pre-restore snapshots are created
- [ ] Result enrichment works (when linked_run_id provided)
- [ ] Comparison view displays correctly
- [ ] Existing staged/evolution flows still work

## Troubleshooting

### Issue: History endpoint returns 500
- Check `app/services/strategies/strategy_restore_service.py` is in correct location
- Verify `STRATEGY_HISTORY_DIR` exists and is writable
- Check application logs for import errors

### Issue: Snapshots not being created
- Verify auto-snapshot code was integrated into source/sidecar/apply services
- Check that operations are being called (add logging if needed)
- Ensure `create_snapshot()` doesn't raise silently in try/except blocks

### Issue: Result summary not showing
- Verify `linked_run_id` is set when snapshot is created
- Check backtest results exist in `user_data/backtest_results/{run_id}/`
- Verify `meta.json` and `parsed_results.json` files are readable

### Issue: History tab doesn't appear
- Clear browser cache (Ctrl+F5)
- Check JavaScript console for errors
- Verify `_initHistoryUI()` is called after strategy selection
