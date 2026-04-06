"""
Utility script to download missing OHLCV data for trading pairs.

Usage:
    python scripts/download_missing_data.py --pairs ETH/USDT BTC/USDT --timeframe 5m --timerange 20250102-20260404
    python scripts/download_missing_data.py --auto-detect --timeframe 5m --timerange 20250102-20260404
"""
import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.runner import start_download, wait_for_run
from app.services.execution_context_service import (
    validate_selected_pair_data,
    normalize_pair_selection,
    resolve_exchange_name,
    read_config_json,
)
from app.core.processes import get_status, get_logs


def main():
    parser = argparse.ArgumentParser(description="Download missing OHLCV data")
    parser.add_argument("--pairs", nargs="+", help="Trading pairs (e.g., ETH/USDT BTC/USDT)")
    parser.add_argument("--timeframe", default="5m", help="Timeframe (default: 5m)")
    parser.add_argument("--timerange", help="Time range in format YYYYMMDD-YYYYMMDD")
    parser.add_argument("--exchange", help="Exchange name (default: from config)")
    parser.add_argument("--auto-detect", action="store_true", help="Auto-detect missing pairs from config")
    parser.add_argument("--wait", action="store_true", help="Wait for download to complete")
    
    args = parser.parse_args()
    
    # Determine pairs to download
    if args.auto_detect:
        cfg = read_config_json()
        pairs = cfg.get("exchange", {}).get("pair_whitelist", [])
        if not pairs:
            print("No pairs found in config. Please specify --pairs manually.")
            sys.exit(1)
        print(f"Auto-detected pairs from config: {', '.join(pairs)}")
    elif args.pairs:
        pairs = args.pairs
    else:
        print("Error: Either --pairs or --auto-detect must be specified")
        parser.print_help()
        sys.exit(1)
    
    # Normalize and validate
    exchange_name = resolve_exchange_name(args.exchange)
    normalized_pairs = normalize_pair_selection(pairs)
    
    print(f"\nChecking data coverage for {len(normalized_pairs)} pairs...")
    print(f"Exchange: {exchange_name}")
    print(f"Timeframe: {args.timeframe}")
    print(f"Timerange: {args.timerange or 'default'}")
    
    _, missing_pairs, issue_details = validate_selected_pair_data(
        pairs=normalized_pairs,
        timeframe=args.timeframe,
        exchange=exchange_name,
        timerange=args.timerange,
    )
    
    if not missing_pairs:
        print("\n✓ All pairs have complete data. No download needed.")
        return
    
    print(f"\n⚠ Found {len(missing_pairs)} pairs with missing/incomplete data:")
    for detail in issue_details:
        print(f"  - {detail}")
    
    print(f"\nStarting download for: {', '.join(missing_pairs)}")
    
    job_id = start_download(
        pairs=missing_pairs,
        timeframe=args.timeframe,
        timerange=args.timerange,
        command_override=None,
    )
    
    print(f"Download job started: {job_id}")
    
    if args.wait:
        print("\nWaiting for download to complete...")
        print("(Press Ctrl+C to stop waiting, download will continue in background)\n")
        
        try:
            import time
            while True:
                status = get_status(job_id)
                if status in ("completed", "failed"):
                    break
                
                logs = get_logs(job_id)
                if logs:
                    print(logs[-1])
                
                time.sleep(2)
            
            final_status = get_status(job_id)
            print(f"\n{'✓' if final_status == 'completed' else '✗'} Download {final_status}")
            
            if final_status == "completed":
                print("\nVerifying data coverage...")
                _, still_missing, _ = validate_selected_pair_data(
                    pairs=normalized_pairs,
                    timeframe=args.timeframe,
                    exchange=exchange_name,
                    timerange=args.timerange,
                )
                if not still_missing:
                    print("✓ All data downloaded successfully!")
                else:
                    print(f"⚠ Still missing data for: {', '.join(still_missing)}")
            else:
                logs = get_logs(job_id)
                print("\nError logs:")
                for log in logs[-10:]:
                    print(f"  {log}")
        
        except KeyboardInterrupt:
            print(f"\n\nDownload continues in background. Job ID: {job_id}")
            print(f"Check status with: curl http://localhost:8000/api/backtest/download-data/{job_id}")
    else:
        print(f"\nDownload running in background. Check status at:")
        print(f"  GET /api/backtest/download-data/{job_id}")


if __name__ == "__main__":
    main()
