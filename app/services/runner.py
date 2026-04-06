from pathlib import Path
from typing import Any, Optional

from app.core.config import STRATEGIES_DIR
from app.core.processes import append_log, get_status, remove_process, set_status
from app.services.command_builder import (
    build_backtest_command,
    build_download_data_command,
    build_hyperopt_command,
)
from app.services.hyperopt_storage import (
    get_hyperopt_run_dir,
    save_hyperopt_logs,
    save_hyperopt_meta,
    save_hyperopt_results,
)
from app.services.runs.backtest_run_service import build_backtest_meta, collect_backtest_run_results
from app.services.runs.base_run_service import build_run_id, normalize_command, wait_for_meta_completion
from app.services.runs.hyperopt_run_service import build_hyperopt_meta, load_hyperopt_run_results
from app.services.runs.run_log_service import log_command_start, log_process_exit, persist_logs
from app.services.runs.run_metadata_service import ensure_valid_strategy_json, finalize_meta
from app.services.runs.run_process_service import mark_running, spawn_and_stream, start_daemon
from app.services.storage import get_run_dir, load_run_meta, save_run_logs, save_run_meta, save_run_results


def wait_for_run(run_id: str, timeout_s: int = 600) -> dict:
    return wait_for_meta_completion(run_id, load_run_meta, get_status, timeout_s=timeout_s)


def start_backtest(
    strategy: str,
    pairs: list[str],
    timeframe: str,
    timerange: Optional[str],
    strategy_params: dict[str, Any],
    exchange: Optional[str] = None,
    strategy_path: Optional[str] = None,
    strategy_label: Optional[str] = None,
    command_override: Optional[list[str]] = None,
    extra_meta: Optional[dict[str, Any]] = None,
) -> str:
    run_id = build_run_id()
    run_dir = get_run_dir(run_id)
    strategy_dir = Path(strategy_path) if strategy_path else STRATEGIES_DIR

    ensure_valid_strategy_json(strategy, run_id, strategy_dir=strategy_dir)

    default_cmd = build_backtest_command(
        strategy=strategy,
        pairs=pairs,
        timeframe=timeframe,
        timerange=timerange,
        strategy_params=strategy_params,
        strategy_path=str(strategy_dir) if strategy_path else None,
        backtest_directory=str(run_dir),
    )
    cmd = normalize_command(default_cmd, command_override)

    display_strategy = strategy_label or strategy
    meta = build_backtest_meta(
        run_id=run_id,
        strategy=strategy,
        display_strategy=display_strategy,
        pairs=pairs,
        timeframe=timeframe,
        timerange=timerange,
        strategy_params=strategy_params,
        strategy_path=str(strategy_dir) if strategy_path else None,
        command=cmd,
        exchange=exchange,
        extra_meta=extra_meta,
    )

    save_run_meta(run_id, meta)
    mark_running(run_id)
    start_daemon(_backtest_worker, run_id, cmd, run_dir, meta)
    return run_id


def start_download(
    pairs: list[str],
    timeframe: str,
    timerange: Optional[str],
    command_override: Optional[list[str]] = None,
) -> str:
    job_id = build_run_id(prefix="dl_")

    default_cmd = build_download_data_command(
        pairs=pairs,
        timeframe=timeframe,
        timerange=timerange,
    )
    cmd = normalize_command(default_cmd, command_override)

    mark_running(job_id)
    start_daemon(_download_worker, job_id, cmd)
    return job_id


def _download_worker(job_id: str, cmd: list[str]) -> None:
    try:
        log_command_start(job_id, cmd)
        code = spawn_and_stream(job_id, cmd)
        if code == 0:
            set_status(job_id, "completed")
        else:
            set_status(job_id, "failed")
            log_process_exit(job_id, code)
    except FileNotFoundError:
        set_status(job_id, "failed")
        append_log(job_id, "ERROR: freqtrade command not found. Please install FreqTrade.")
    except Exception as exc:
        set_status(job_id, "failed")
        append_log(job_id, f"ERROR: {str(exc)}")
    finally:
        remove_process(job_id)


def _backtest_worker(run_id: str, cmd: list[str], run_dir: Path, meta: dict[str, Any]) -> None:
    try:
        log_command_start(run_id, cmd)
        code = spawn_and_stream(run_id, cmd)
        if code == 0:
            outcome = collect_backtest_run_results(run_dir, meta)
            set_status(run_id, outcome["status"])
            if outcome.get("log_message"):
                append_log(run_id, outcome["log_message"])
            if outcome.get("error"):
                meta["error"] = outcome["error"]
            meta["raw_artifact"] = outcome.get("raw_artifact", {"available": False})
            if outcome.get("results") is not None:
                save_run_results(run_id, outcome["results"])
        else:
            set_status(run_id, "failed")
            log_process_exit(run_id, code)

        save_run_meta(run_id, finalize_meta(meta, get_status(run_id)))
        persist_logs(run_id, save_run_logs)
    except FileNotFoundError:
        set_status(run_id, "failed")
        append_log(run_id, "ERROR: freqtrade command not found. Please install FreqTrade.")
        save_run_meta(run_id, finalize_meta(meta, "failed", "freqtrade not found"))
        persist_logs(run_id, save_run_logs)
    except Exception as exc:
        set_status(run_id, "failed")
        append_log(run_id, f"ERROR: {str(exc)}")
        save_run_meta(run_id, finalize_meta(meta, "failed", str(exc)))
        persist_logs(run_id, save_run_logs)
    finally:
        remove_process(run_id)


def start_hyperopt(
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
    command_override: Optional[list[str]] = None,
) -> str:
    run_id = build_run_id(prefix="ho_")
    run_dir = get_hyperopt_run_dir(run_id)

    default_cmd = build_hyperopt_command(
        strategy=strategy,
        pairs=pairs,
        timeframe=timeframe,
        timerange=timerange,
        epochs=epochs,
        spaces=spaces,
        loss_function=loss_function,
        jobs=jobs,
        min_trades=min_trades,
        early_stop=early_stop,
        dry_run_wallet=dry_run_wallet,
        max_open_trades=max_open_trades,
        stake_amount=stake_amount,
        exchange=exchange,
        random_state=random_state,
    )
    cmd = normalize_command(default_cmd, command_override)

    meta = build_hyperopt_meta(
        run_id=run_id,
        strategy=strategy,
        pairs=pairs,
        timeframe=timeframe,
        timerange=timerange,
        epochs=epochs,
        spaces=spaces,
        loss_function=loss_function,
        jobs=jobs,
        min_trades=min_trades,
        early_stop=early_stop,
        dry_run_wallet=dry_run_wallet,
        max_open_trades=max_open_trades,
        stake_amount=stake_amount,
        exchange=exchange,
        command=cmd,
    )
    save_hyperopt_meta(run_id, meta)

    ensure_valid_strategy_json(strategy, run_id)
    mark_running(run_id)
    start_daemon(_hyperopt_worker, run_id, cmd, run_dir, meta, strategy)
    return run_id


def _hyperopt_worker(run_id: str, cmd: list[str], run_dir: Path, meta: dict[str, Any], strategy: str) -> None:
    try:
        log_command_start(run_id, cmd)
        code = spawn_and_stream(run_id, cmd)
        if code == 0:
            set_status(run_id, "completed")
            results = load_hyperopt_run_results(run_dir, strategy)
            save_hyperopt_results(run_id, results)
        else:
            set_status(run_id, "failed")
            log_process_exit(run_id, code)

        save_hyperopt_meta(run_id, finalize_meta(meta, get_status(run_id)))
        persist_logs(run_id, save_hyperopt_logs)
    except FileNotFoundError:
        set_status(run_id, "failed")
        append_log(run_id, "ERROR: freqtrade command not found.")
        save_hyperopt_meta(run_id, finalize_meta(meta, "failed", "freqtrade not found"))
        persist_logs(run_id, save_hyperopt_logs)
    except Exception as exc:
        set_status(run_id, "failed")
        append_log(run_id, f"ERROR: {str(exc)}")
        save_hyperopt_meta(run_id, finalize_meta(meta, "failed", str(exc)))
        persist_logs(run_id, save_hyperopt_logs)
    finally:
        remove_process(run_id)
