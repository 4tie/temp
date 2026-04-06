import re
from datetime import datetime, timezone
from typing import Any, Optional
from app.core.config import (
    BACKTEST_RESULTS_DIR,
    DATA_DIR,
    BASE_DIR,
    FREQTRADE_CONFIG_FILE,
    PYTHON_EXECUTABLE,
    STRATEGIES_DIR,
)


_TIMERANGE_RE = re.compile(r"^(\d{8})-(\d{8})$")
_DEFAULT_DOWNLOAD_START = "20240101"


def _today_yyyymmdd() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _effective_download_timerange(timerange: Optional[str]) -> str:
    today = _today_yyyymmdd()
    if not timerange:
        return f"{_DEFAULT_DOWNLOAD_START}-{today}"

    value = timerange.strip()
    if not _TIMERANGE_RE.match(value):
        return value
    return value


def build_backtest_command(
    strategy: str,
    pairs: list[str],
    timeframe: str,
    timerange: Optional[str],
    strategy_params: dict[str, Any],
    strategy_path: Optional[str] = None,
    backtest_directory: Optional[str] = None,
) -> list[str]:
    output_directory = backtest_directory or str(BACKTEST_RESULTS_DIR / strategy)
    cmd = [
        PYTHON_EXECUTABLE, "-m", "freqtrade", "backtesting",
        "-c", str(FREQTRADE_CONFIG_FILE),
        "--strategy", strategy,
        "--timeframe", timeframe,
        "--export", "trades",
        "--backtest-directory", output_directory,
    ]

    if strategy_path:
        cmd.extend(["--strategy-path", strategy_path])

    if timerange:
        cmd.extend(["--timerange", timerange])

    if pairs:
        cmd.extend(["--pairs"] + pairs)

    for key, value in strategy_params.items():
        cmd.extend(["--strategy-opt", f"{key}={value}"])

    return cmd


def build_download_data_command(
    pairs: list[str],
    timeframe: str,
    timerange: Optional[str],
) -> list[str]:
    cmd = [
        PYTHON_EXECUTABLE, "-m", "freqtrade", "download-data",
        "-c", str(FREQTRADE_CONFIG_FILE),
        "--timeframes", timeframe,
        "--timerange", _effective_download_timerange(timerange),
        "--prepend",
    ]

    if pairs:
        cmd.extend(["--pairs"] + pairs)

    return cmd


def build_hyperopt_command(
    strategy: str,
    pairs: list[str],
    timeframe: str,
    timerange: Optional[str],
    epochs: int,
    spaces: list[str],
    loss_function: str,
    jobs: int,
    min_trades: int,
    early_stop: Optional[int],
    dry_run_wallet: float,
    max_open_trades: int,
    stake_amount: str,
    exchange: str,
    random_state: Optional[int],
) -> list[str]:
    cmd = [
        PYTHON_EXECUTABLE, "-m", "freqtrade", "hyperopt",
        "--strategy", strategy,
        "--timeframe", timeframe,
        "--epochs", str(epochs),
        "--spaces"] + spaces + [
        "--hyperopt-loss", loss_function,
        "-j", str(jobs),
        "--min-trades", str(min_trades),
        "--dry-run-wallet", str(dry_run_wallet),
        "--max-open-trades", str(max_open_trades),
        "--stake-amount", stake_amount,
        "--datadir", str(DATA_DIR),
        "--strategy-path", str(STRATEGIES_DIR),
        "--print-json",
    ]

    if FREQTRADE_CONFIG_FILE.exists():
        cmd.extend(["--config", str(FREQTRADE_CONFIG_FILE)])

    if timerange:
        cmd.extend(["--timerange", timerange])

    if pairs:
        cmd.extend(["--pairs"] + pairs)

    if early_stop is not None:
        cmd.extend(["--early-stop", str(early_stop)])

    if random_state is not None:
        cmd.extend(["--random-state", str(random_state)])

    return cmd
