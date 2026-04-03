from pathlib import Path
from typing import Any

from app.core.config import DATA_DIR


def check_data_coverage(pairs: list[str], timeframe: str, exchange: str) -> list[dict[str, Any]]:
    coverage = []
    search_dirs = [DATA_DIR / exchange, DATA_DIR]

    for pair in pairs:
        pair_file_name = pair.replace("/", "_")

        found = False
        file_size = 0
        file_path_str = ""

        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
            for ext in [".feather", ".json", ".json.gz", ".hdf5"]:
                candidate = search_dir / f"{pair_file_name}-{timeframe}{ext}"
                if candidate.exists():
                    found = True
                    file_size = candidate.stat().st_size
                    file_path_str = str(candidate)
                    break
            if found:
                break

        coverage.append({
            "pair": pair,
            "timeframe": timeframe,
            "exchange": exchange,
            "available": found,
            "file_size": file_size,
            "file_path": file_path_str,
        })

    return coverage
