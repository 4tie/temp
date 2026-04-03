"""
One-time migration script: convert strategy JSON files from the custom nested
app format to the flat Freqtrade-compatible format.

Old format (nested, app-specific):
{
  "strategy": "...",
  "settings": { ... },
  "parameters": {
    "param_name": {
      "type": "IntParameter",
      "value": 4,
      ...
    }
  }
}

New format (flat, Freqtrade-compatible):
{
  "param_name": 4,
  ...
}

Usage:
    python scripts/migrate_strategy_json.py [--dry-run]

Already-flat files are left unchanged. Files with empty or missing
"parameters" sections are written as {}.
"""

import argparse
import json
import sys
from pathlib import Path

STRATEGIES_DIR = Path(__file__).parent.parent / "user_data" / "strategies"


def is_nested_format(data: dict) -> bool:
    return "parameters" in data and isinstance(data["parameters"], dict)


def migrate_file(json_file: Path, dry_run: bool = False) -> dict:
    try:
        data = json.loads(json_file.read_text())
    except json.JSONDecodeError as e:
        return {"file": json_file.name, "status": "error", "detail": str(e)}

    if not isinstance(data, dict):
        return {"file": json_file.name, "status": "skip", "detail": "not a JSON object"}

    if not is_nested_format(data):
        return {"file": json_file.name, "status": "already_flat", "detail": "no nested 'parameters' section"}

    parameters = data["parameters"]
    flat: dict = {}
    for param_name, param_info in parameters.items():
        if isinstance(param_info, dict) and "value" in param_info:
            flat[param_name] = param_info["value"]
        else:
            flat[param_name] = param_info

    if not dry_run:
        json_file.write_text(json.dumps(flat, indent=2))

    return {"file": json_file.name, "status": "migrated", "params": list(flat.keys())}


def validate_flat(json_file: Path) -> dict:
    try:
        data = json.loads(json_file.read_text())
    except json.JSONDecodeError as e:
        return {"file": json_file.name, "ok": False, "detail": str(e)}

    if not isinstance(data, dict):
        return {"file": json_file.name, "ok": False, "detail": "not a JSON object"}

    if is_nested_format(data):
        return {"file": json_file.name, "ok": False, "detail": "still in nested format"}

    for k, v in data.items():
        if isinstance(v, dict):
            return {"file": json_file.name, "ok": False, "detail": f"param '{k}' is still a dict"}

    return {"file": json_file.name, "ok": True, "params": list(data.keys())}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without writing files")
    parser.add_argument("--validate", action="store_true", help="Validate files are flat without migrating")
    args = parser.parse_args()

    json_files = sorted(STRATEGIES_DIR.glob("*.json"))
    if not json_files:
        print(f"No JSON files found in {STRATEGIES_DIR}")
        sys.exit(0)

    if args.validate:
        print(f"Validating {len(json_files)} strategy JSON files in {STRATEGIES_DIR}\n")
        all_ok = True
        for f in json_files:
            result = validate_flat(f)
            status = "OK" if result["ok"] else "FAIL"
            detail = result.get("detail", "")
            params = result.get("params", [])
            if result["ok"]:
                print(f"  [{status}] {result['file']}: {len(params)} params")
            else:
                print(f"  [{status}] {result['file']}: {detail}")
                all_ok = False
        print()
        if all_ok:
            print("All files are in flat Freqtrade-compatible format.")
        else:
            print("Some files are not flat. Run without --validate to migrate.")
            sys.exit(1)
        return

    prefix = "[DRY RUN] " if args.dry_run else ""
    print(f"{prefix}Migrating {len(json_files)} strategy JSON files in {STRATEGIES_DIR}\n")

    migrated = skipped = errors = 0
    for f in json_files:
        result = migrate_file(f, dry_run=args.dry_run)
        status = result["status"]
        if status == "migrated":
            params = result.get("params", [])
            print(f"  {prefix}MIGRATED {result['file']}: {params}")
            migrated += 1
        elif status == "already_flat":
            print(f"  SKIP     {result['file']}: {result['detail']}")
            skipped += 1
        else:
            print(f"  ERROR    {result['file']}: {result['detail']}")
            errors += 1

    print(f"\nDone. Migrated: {migrated}, Already flat: {skipped}, Errors: {errors}")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
