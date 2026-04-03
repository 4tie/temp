from typing import Any, Optional
from app.core.config import STRATEGIES_DIR, DATA_DIR, FREQTRADE_CONFIG_DIR, HYPEROPT_RESULTS_DIR, BASE_DIR, PYTHON_EXECUTABLE


def build_backtest_command(
    strategy: str,
    pairs: list[str],
    timeframe: str,
    timerange: Optional[str],
    strategy_params: dict[str, Any],
) -> list[str]:
    cmd = [
        PYTHON_EXECUTABLE, "-m", "freqtrade", "backtesting",
        "-c", "user_data/config.json",
        "--timeframe", timeframe,
        "--export", "trades",
        "--export-filename", f"user_data/backtest_results/{strategy}/result.json",
    ]

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
) -> list[str]:
    cmd = [
        PYTHON_EXECUTABLE, "-m", "freqtrade", "download-data",
        "-c", "user_data/config.json",
        "--timeframe", timeframe,
        "--timerange", "20251001-20260321",
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
        "freqtrade", "hyperopt",
        "--userdir", str(BASE_DIR),
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

    config_file = FREQTRADE_CONFIG_DIR / "config.json"
    if config_file.exists():
        cmd.extend(["--config", str(config_file)])

    if timerange:
        cmd.extend(["--timerange", timerange])

    if pairs:
        cmd.extend(["--pairs"] + pairs)

    if early_stop is not None:
        cmd.extend(["--early-stop", str(early_stop)])

    if random_state is not None:
        cmd.extend(["--random-state", str(random_state)])

    return cmd
