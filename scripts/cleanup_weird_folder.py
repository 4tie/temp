r"""
Cleanup script to remove incorrectly created nested user_data directories.

This fixes the issue where FreqTrade created:
T:\SameGrossNetframework\SameGrossNetframework\TSameGrossNetframeworkSameGrossNetframeworkuser_data

Instead of using:
T:\SameGrossNetframework\SameGrossNetframework\user_data
"""
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
WEIRD_FOLDER = PROJECT_ROOT / "TSameGrossNetframeworkSameGrossNetframeworkuser_data"
CORRECT_FOLDER = PROJECT_ROOT / "user_data"

def main():
    if not WEIRD_FOLDER.exists():
        print(f"[OK] No weird folder found. Everything is clean!")
        print(f"  Checked: {WEIRD_FOLDER}")
        return
    
    print(f"Found incorrectly created folder:")
    print(f"  {WEIRD_FOLDER}")
    
    # Check if it has any important data
    has_data = False
    if WEIRD_FOLDER.is_dir():
        for item in WEIRD_FOLDER.rglob("*"):
            if item.is_file() and item.stat().st_size > 0:
                has_data = True
                break
    
    if has_data:
        print(f"\n[WARNING] This folder contains data!")
        print(f"  You may want to manually review and move important files to:")
        print(f"  {CORRECT_FOLDER}")
        
        response = input("\nDelete anyway? (yes/no): ").strip().lower()
        if response != "yes":
            print("Cancelled. No changes made.")
            return
    
    print(f"\nDeleting: {WEIRD_FOLDER}")
    try:
        shutil.rmtree(WEIRD_FOLDER)
        print(f"[OK] Successfully deleted weird folder")
        print(f"\nFreqTrade will now use the correct folder:")
        print(f"  {CORRECT_FOLDER}")
    except Exception as e:
        print(f"[ERROR] Error deleting folder: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
