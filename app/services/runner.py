import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

from app.core.config import (
    BACKTEST_RESULTS_DIR,
    DATA_DIR,
    RAW_ARTIFACT_META_SUFFIX,
    STRATEGIES_DIR,
)
from app.core.processes import (
    append_log, set_status, get_status,
    set_process, get_logs, remove_process
)
from app.services.command_builder import build_backtest_command, build_download_data_command, build_hyperopt_command
from app.services.result_parser import parse_backtest_results, find_run_local_result_artifact
from app.services.storage import (
    save_run_meta,
    save_run_results,
    save_run_logs,
    get_run_dir,
    load_run_meta,
)
from app.services.hyperopt_storage import save_hyperopt_meta, save_hyperopt_results, save_hyperopt_logs, get_hyperopt_run_dir
from app.services.runs.base_run_service import build_run_id, normalize_command, wait_for_meta_completion
from app.services.runs.backtest_run_service import build_backtest_meta
from app.services.runs.backtest_run_service import try_import_fresh_global_result
from app.services.runs.hyperopt_run_service import build_hyperopt_meta, copy_hyperopt_results
from app.services.runs.run_log_service import log_command_start, log_process_exit, persist_logs
from app.services.runs.run_metadata_service import ensure_valid_strategy_json, finalize_meta, read_runtime_config
from app.services.runs.run_process_service import mark_running, start_daemon


def _normalized_command(default_cmd: list[str], command_override: Optional[list[str]]) -> list[str]:
    return normalize_command(default_cmd, command_override)


def _read_runtime_config() -> dict[str, Any]:
    return read_runtime_config()


def _ensure_valid_strategy_json(strategy: str, run_id: str, strategy_dir: Path | None = None) -> None:
    ensure_valid_strategy_json(strategy, run_id, strategy_dir=strategy_dir)


def _spawn_and_stream(run_id: str, cmd: list[str]) -> int:
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    set_process(run_id, proc)
    for line in proc.stdout:
        append_log(run_id, line.rstrip())
    proc.wait()
    return proc.returncode


def _try_import_fresh_global_result(run_dir: Path, meta: dict[str, Any]) -> bool:
    return try_import_fresh_global_result(run_dir, meta)


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

    _ensure_valid_strategy_json(strategy, run_id, strategy_dir=strategy_dir)

    default_cmd = build_backtest_command(
        strategy=strategy,
        pairs=pairs,
        timeframe=timeframe,
        timerange=timerange,
        strategy_params=strategy_params,
        strategy_path=str(strategy_dir) if strategy_path else None,
        backtest_directory=str(run_dir),
    )
    cmd = _normalized_command(default_cmd, command_override)

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

    _run_subprocess(run_id, cmd, run_dir, meta)
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
    cmd = _normalized_command(default_cmd, command_override)

    mark_running(job_id)

    start_daemon(_download_worker, job_id, cmd)

    return job_id


def _download_worker(job_id: str, cmd: list[str]):
    try:
        log_command_start(job_id, cmd)
        code = _spawn_and_stream(job_id, cmd)
        if code == 0:
            set_status(job_id, "completed")
        else:
            set_status(job_id, "failed")
            log_process_exit(job_id, code)
    except FileNotFoundError:
        set_status(job_id, "failed")
        append_log(job_id, "ERROR: freqtrade command not found. Please install FreqTrade.")
    except Exception as e:
        set_status(job_id, "failed")
        append_log(job_id, f"ERROR: {str(e)}")


def _run_subprocess(run_id: str, cmd: list[str], run_dir: Path, meta: dict):
    start_daemon(_backtest_worker, run_id, cmd, run_dir, meta)


def _backtest_worker(run_id: str, cmd: list[str], run_dir: Path, meta: dict):
    try:
        log_command_start(run_id, cmd)
        code = _spawn_and_stream(run_id, cmd)
        if code == 0:
            artifact = find_run_local_result_artifact(run_dir)
            if not artifact.get("available"):
                imported = _try_import_fresh_global_result(run_dir, meta)
                if imported:
                    artifact = find_run_local_result_artifact(run_dir)

            if not artifact.get("available"):
                set_status(run_id, "failed")
                append_log(
                    run_id,
                    "ERROR: Backtest completed but no attributable result artifact was found for this run.",
                )
                meta["error"] = "missing run-local result artifact"
                meta["raw_artifact"] = {"available": False, "run_local": False}
            else:
                results = parse_backtest_results(run_dir)
                results["display_strategy"] = meta.get("display_strategy") or meta.get("strategy")
                if results.get("error"):
                    set_status(run_id, "failed")
                    append_log(run_id, f"ERROR: Failed to parse run-local result artifact: {results.get('error')}")
                    meta["error"] = f"result parse error: {results.get('error')}"
                else:
                    set_status(run_id, "completed")
                save_run_results(run_id, results)
                meta["raw_artifact"] = results.get("raw_artifact", {"available": False})
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
    except Exception as e:
        set_status(run_id, "failed")
        append_log(run_id, f"ERROR: {str(e)}")
        save_run_meta(run_id, finalize_meta(meta, "failed", str(e)))
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
    cmd = _normalized_command(default_cmd, command_override)

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

    start_daemon(_hyperopt_worker, run_id, cmd, run_dir, meta, strategy)

    return run_id

def _hyperopt_worker(run_id: str, cmd: list[str], run_dir: Path, meta: dict, strategy: str):
    try:
        log_command_start(run_id, cmd)
        code = _spawn_and_stream(run_id, cmd)
        if code == 0:
            set_status(run_id, "completed")
            copy_hyperopt_results(run_dir, strategy)
            from app.services.hyperopt_parser import parse_hyperopt_results, load_params_file
            results = parse_hyperopt_results(run_dir, strategy)

            exported_params = load_params_file(strategy)
            if exported_params:
                results["exported_params"] = exported_params

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
    except Exception as e:
        set_status(run_id, "failed")
        append_log(run_id, f"ERROR: {str(e)}")
        save_hyperopt_meta(run_id, finalize_meta(meta, "failed", str(e)))
        persist_logs(run_id, save_hyperopt_logs)
    finally:
        remove_process(run_id)
