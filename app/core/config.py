import os
from pathlib import Path

BASE_DIR = Path(os.environ.get("USER_DATA_DIR", Path(__file__).resolve().parents[3] / "user_data"))
BACKTEST_RESULTS_DIR = BASE_DIR / "backtest_results"
HYPEROPT_RESULTS_DIR = BASE_DIR / "hyperopt_results"
STRATEGIES_DIR = BASE_DIR / "strategies"
DATA_DIR = BASE_DIR / "data"
PRESETS_FILE = BASE_DIR / "presets.json"
LAST_CONFIG_FILE = BASE_DIR / "last_config.json"
FREQTRADE_CONFIG_DIR = BASE_DIR

BACKTEST_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
HYPEROPT_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
STRATEGIES_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

PORT = int(os.environ.get("BACKTEST_API_PORT", "8000"))

VALID_TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"]

DEFAULT_EXCHANGE = os.environ.get("FREQTRADE_EXCHANGE", "binance")
