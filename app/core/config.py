import os
import sys
from pathlib import Path

# Resolve BASE_DIR to absolute path to avoid path concatenation issues
_default_base = Path(__file__).resolve().parents[2] / "user_data"
BASE_DIR = Path(os.environ.get("USER_DATA_DIR", str(_default_base))).resolve()
USER_DATA_ROOT = BASE_DIR
BACKTEST_RESULTS_DIR = BASE_DIR / "backtest_results"
HYPEROPT_RESULTS_DIR = BASE_DIR / "hyperopt_results"
HYPEROPT_RUNS_DIR = HYPEROPT_RESULTS_DIR / "runs"
STRATEGIES_DIR = BASE_DIR / "strategies"
DATA_DIR = BASE_DIR / "data"
PRESETS_FILE = BASE_DIR / "presets.json"
LAST_CONFIG_FILE = BASE_DIR / "last_config.json"
FREQTRADE_CONFIG_DIR = BASE_DIR
FREQTRADE_CONFIG_FILE = FREQTRADE_CONFIG_DIR / "config.json"

AI_CONVERSATIONS_DIR = BASE_DIR / "ai_conversations"
AI_THREADS_DIR = BASE_DIR / "ai_threads"
AI_EVOLUTION_DIR = BASE_DIR / "ai_evolution"
AI_LOOP_STATE_DIR = BASE_DIR / "ai_loop_state"
AI_LOOP_REPORTS_DIR = BASE_DIR / "ai_loop_reports"
AI_PIPELINE_LOGS_DIR = BASE_DIR / "ai_pipeline_logs"
AI_MODEL_METRICS_FILE = BASE_DIR / "ai_model_metrics.json"
APP_RUNTIME_DIR = BASE_DIR / "runtime"

RUN_META_FILENAME = "meta.json"
PARSED_RESULTS_FILENAME = "parsed_results.json"
RAW_ARTIFACT_META_SUFFIX = ".meta.json"
RUN_LOGS_FILENAME = "logs.txt"
DEV_SERVER_PID_FILENAME = "dev_server.pid.json"
DEV_SERVER_LOG_FILENAME = "dev_server.log"
APP_EVENT_LOG_FILENAME = "app_events.jsonl"
DEV_SERVER_PID_FILE = APP_RUNTIME_DIR / DEV_SERVER_PID_FILENAME
DEV_SERVER_LOG_FILE = APP_RUNTIME_DIR / DEV_SERVER_LOG_FILENAME
APP_EVENT_LOG_FILE = APP_RUNTIME_DIR / APP_EVENT_LOG_FILENAME
AI_LOOP_STATE_FILE = AI_LOOP_STATE_DIR / "sessions.json"

BACKTEST_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
HYPEROPT_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
HYPEROPT_RUNS_DIR.mkdir(parents=True, exist_ok=True)
STRATEGIES_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
AI_CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)
AI_THREADS_DIR.mkdir(parents=True, exist_ok=True)
AI_EVOLUTION_DIR.mkdir(parents=True, exist_ok=True)
AI_LOOP_STATE_DIR.mkdir(parents=True, exist_ok=True)
AI_LOOP_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
AI_PIPELINE_LOGS_DIR.mkdir(parents=True, exist_ok=True)
APP_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

HOST = os.environ.get("BACKTEST_API_HOST", "127.0.0.1")
PORT = int(os.environ.get("BACKTEST_API_PORT", "8000"))

VALID_TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"]

DEFAULT_EXCHANGE = os.environ.get("FREQTRADE_EXCHANGE", "binance")

PYTHON_EXECUTABLE = os.environ.get("FREQTRADE_PYTHON", sys.executable)
