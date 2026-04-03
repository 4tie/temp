import asyncio
import json
import shutil
import subprocess
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.core.config import BACKTEST_RESULTS_DIR, HYPEROPT_RESULTS_DIR, DATA_DIR, STRATEGIES_DIR
from app.core.processes import (
    set_process, append_log, set_status, get_status,
    get_logs, remove_process, get_process
)
from app.services.command_builder import build_backtest_command, build_download_data_command, build_hyperopt_command
from app.services.result_parser import parse_backtest_results
from app.services.storage import save_run_meta, save_run_results, save_run_logs, get_run_dir, load_run_meta
from app.services.hyperopt_storage import save_hyperopt_meta, save_hyperopt_results, save_hyperopt_logs, get_hyperopt_run_dir


_JSON_SCALAR_TYPES = (str, int, float, bool, type(None))


def wait_for_run(run_id: str, timeout_s: int = 600) -> dict:
    """Block until a backtest run finishes or timeout. Returns final meta dict."""
    import time as _time
    deadline = _time.monotonic() + timeout_s
    while _time.monotonic() < deadline:
        meta = load_run_meta(run_id)
        if meta and meta.get("status") not in ("running", None):
            return meta
        status = get_status(run_id)
        if status not in ("running", "unknown"):
            return load_run_meta(run_id) or {"run_id": run_id, "status": status}
        _time.sleep(5)
    return load_run_meta(run_id) or {"run_id": run_id, "status": "timeout"}


def _ensure_valid_strategy_json(strategy: str, run_id: str) -> None:
    json_path = STRATEGIES_DIR / f"{strategy}.json"
    if not json_path.exists():
        return
    try:
        raw = json_path.read_bytes()
        if not raw.strip():
            raise ValueError("empty file")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("not a dict")
        # Support legacy flat format: migrate to nested {"strategy_name": ..., "params": {"buy": {}, "sell": {}}}
        if "params" not in data:
            nested: dict = {"buy": {}, "sell": {}}
            for k, v in data.items():
                if not isinstance(v, _JSON_SCALAR_TYPES):
                    raise ValueError(f"non-scalar value: {type(v).__name__}")
                space = "sell" if k.startswith("sell_") else "buy"
                nested[space][k] = v
            data = {"strategy_name": strategy, "params": nested}
            json_path.write_text(json.dumps(data, indent=2))
            append_log(run_id, f"INFO: {strategy}.json migrated to nested params format.")
            return
        if "strategy_name" not in data:
            data["strategy_name"] = strategy
            json_path.write_text(json.dumps(data, indent=2))
        params = data["params"]
        if not isinstance(params, dict):
            raise ValueError("params is not a dict")
        for space_vals in params.values():
            if not isinstance(space_vals, dict):
                raise ValueError("space values must be a dict")
            for v in space_vals.values():
                if not isinstance(v, _JSON_SCALAR_TYPES):
                    raise ValueError(f"non-scalar value: {type(v).__name__}")
    except Exception as exc:
        json_path.write_text(json.dumps({"strategy_name": strategy, "params": {}}, indent=2))
        append_log(
            run_id,
            f"WARNING: {strategy}.json was invalid ({exc}); reset so FreqTrade uses class defaults.",
        )


def start_backtest(
    strategy: str,
    pairs: list[str],
    timeframe: str,
    timerange: Optional[str],
    strategy_params: dict[str, Any],
) -> str:
    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    run_dir = BACKTEST_RESULTS_DIR / strategy
    run_dir.mkdir(parents=True, exist_ok=True)

    _ensure_valid_strategy_json(strategy, run_id)

    cmd = build_backtest_command(
        strategy=strategy,
        pairs=pairs,
        timeframe=timeframe,
        timerange=timerange,
        strategy_params=strategy_params,
    )

    config_file = BACKTEST_RESULTS_DIR.parent / "config.json"
    dry_run_wallet = None
    max_open_trades = None
    stake_amount = None
    if config_file.exists():
        try:
            cfg = json.loads(config_file.read_text())
            dry_run_wallet = cfg.get("dry_run_wallet")
            max_open_trades = cfg.get("max_open_trades")
            stake_amount = cfg.get("stake_amount")
        except Exception:
            pass

    meta = {
        "run_id": run_id,
        "strategy": strategy,
        "pairs": pairs,
        "timeframe": timeframe,
        "timerange": timerange,
        "dry_run_wallet": dry_run_wallet,
        "max_open_trades": max_open_trades,
        "stake_amount": stake_amount,
        "strategy_params": strategy_params,
        "command": cmd,
        "status": "running",
        "started_at": datetime.utcnow().isoformat(),
        "completed_at": None,
    }
    save_run_meta(run_id, meta)

    _run_subprocess(run_id, cmd, run_dir, meta)
    return run_id


def start_download(
    pairs: list[str],
    timeframe: str,
) -> str:
    job_id = "dl_" + datetime.utcnow().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]

    cmd = build_download_data_command(
        pairs=pairs,
        timeframe=timeframe,
    )

    set_status(job_id, "running")
    set_process(job_id, None)

    thread = threading.Thread(target=_download_worker, args=(job_id, cmd), daemon=True)
    thread.start()

    return job_id


def _download_worker(job_id: str, cmd: list[str]):
    try:
        append_log(job_id, f"$ {' '.join(cmd)}")
        append_log(job_id, "")
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        set_process(job_id, proc)

        for line in proc.stdout:
            append_log(job_id, line.rstrip())

        proc.wait()

        if proc.returncode == 0:
            set_status(job_id, "completed")
        else:
            set_status(job_id, "failed")
            append_log(job_id, f"Process exited with code {proc.returncode}")
    except FileNotFoundError:
        set_status(job_id, "failed")
        append_log(job_id, "ERROR: freqtrade command not found. Please install FreqTrade.")
    except Exception as e:
        set_status(job_id, "failed")
        append_log(job_id, f"ERROR: {str(e)}")


def _run_subprocess(run_id: str, cmd: list[str], run_dir: Path, meta: dict):
    thread = threading.Thread(target=_backtest_worker, args=(run_id, cmd, run_dir, meta), daemon=True)
    thread.start()


def _copy_latest_result(run_dir: Path):
    last_result_file = BACKTEST_RESULTS_DIR / ".last_result.json"
    if not last_result_file.exists():
        return
    try:
        last_ref = json.loads(last_result_file.read_text())
        latest_name = last_ref.get("latest_backtest", "")
        if not latest_name:
            return
        latest_path = BACKTEST_RESULTS_DIR / latest_name
        if latest_path.exists():
            shutil.copy2(latest_path, run_dir / latest_path.name)
            meta_name = latest_name.replace(".zip", ".meta.json")
            meta_path = BACKTEST_RESULTS_DIR / meta_name
            if meta_path.exists():
                shutil.copy2(meta_path, run_dir / meta_path.name)
    except (json.JSONDecodeError, OSError):
        pass


def _backtest_worker(run_id: str, cmd: list[str], run_dir: Path, meta: dict):
    try:
        append_log(run_id, f"$ {' '.join(cmd)}")
        append_log(run_id, "")
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

        if proc.returncode == 0:
            set_status(run_id, "completed")
            _copy_latest_result(run_dir)
            results = parse_backtest_results(run_dir)
            save_run_results(run_id, results)
        else:
            set_status(run_id, "failed")
            append_log(run_id, f"Process exited with code {proc.returncode}")

        meta["status"] = get_status(run_id)
        meta["completed_at"] = datetime.utcnow().isoformat()
        save_run_meta(run_id, meta)
        save_run_logs(run_id, get_logs(run_id))

    except FileNotFoundError:
        set_status(run_id, "failed")
        append_log(run_id, "ERROR: freqtrade command not found. Please install FreqTrade.")
        meta["status"] = "failed"
        meta["error"] = "freqtrade not found"
        meta["completed_at"] = datetime.utcnow().isoformat()
        save_run_meta(run_id, meta)
        save_run_logs(run_id, get_logs(run_id))
    except Exception as e:
        set_status(run_id, "failed")
        append_log(run_id, f"ERROR: {str(e)}")
        meta["status"] = "failed"
        meta["error"] = str(e)
        meta["completed_at"] = datetime.utcnow().isoformat()
        save_run_meta(run_id, meta)
        save_run_logs(run_id, get_logs(run_id))
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
) -> str:
    run_id = "ho_" + datetime.utcnow().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    run_dir = get_hyperopt_run_dir(run_id)

    cmd = build_hyperopt_command(
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

    meta = {
        "run_id": run_id,
        "type": "hyperopt",
        "strategy": strategy,
        "pairs": pairs,
        "timeframe": timeframe,
        "timerange": timerange,
        "epochs": epochs,
        "spaces": spaces,
        "loss_function": loss_function,
        "jobs": jobs,
        "min_trades": min_trades,
        "early_stop": early_stop,
        "dry_run_wallet": dry_run_wallet,
        "max_open_trades": max_open_trades,
        "stake_amount": stake_amount,
        "exchange": exchange,
        "command": cmd,
        "status": "running",
        "started_at": datetime.utcnow().isoformat(),
        "completed_at": None,
    }
    save_hyperopt_meta(run_id, meta)

    _ensure_valid_strategy_json(strategy, run_id)

    thread = threading.Thread(target=_hyperopt_worker, args=(run_id, cmd, run_dir, meta, strategy), daemon=True)
    thread.start()

    return run_id


def _copy_hyperopt_results(run_dir: Path, strategy: str):
    last_file = HYPEROPT_RESULTS_DIR / ".last_hyperopt.json"
    if last_file.exists():
        try:
            ref = json.loads(last_file.read_text())
            latest_name = ref.get("latest_hyperopt", "")
            if latest_name:
                src = HYPEROPT_RESULTS_DIR / latest_name
                if src.exists():
                    shutil.copy2(src, run_dir / src.name)
                    return
        except (json.JSONDecodeError, OSError):
            pass

    if HYPEROPT_RESULTS_DIR.exists():
        fthypt_files = list(HYPEROPT_RESULTS_DIR.glob(f"strategy_{strategy}_*.fthypt"))
        if not fthypt_files:
            fthypt_files = list(HYPEROPT_RESULTS_DIR.glob("*.fthypt"))
        if fthypt_files:
            latest = sorted(fthypt_files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
            shutil.copy2(latest, run_dir / latest.name)


def _hyperopt_worker(run_id: str, cmd: list[str], run_dir: Path, meta: dict, strategy: str):
    try:
        append_log(run_id, f"$ {' '.join(cmd)}")
        append_log(run_id, "")
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

        if proc.returncode == 0:
            set_status(run_id, "completed")
            _copy_hyperopt_results(run_dir, strategy)
            from app.services.hyperopt_parser import parse_hyperopt_results, load_params_file
            results = parse_hyperopt_results(run_dir, strategy)

            exported_params = load_params_file(strategy)
            if exported_params:
                results["exported_params"] = exported_params

            save_hyperopt_results(run_id, results)
        else:
            set_status(run_id, "failed")
            append_log(run_id, f"Process exited with code {proc.returncode}")

        meta["status"] = get_status(run_id)
        meta["completed_at"] = datetime.utcnow().isoformat()
        save_hyperopt_meta(run_id, meta)
        save_hyperopt_logs(run_id, get_logs(run_id))

    except FileNotFoundError:
        set_status(run_id, "failed")
        append_log(run_id, "ERROR: freqtrade command not found.")
        meta["status"] = "failed"
        meta["error"] = "freqtrade not found"
        meta["completed_at"] = datetime.utcnow().isoformat()
        save_hyperopt_meta(run_id, meta)
        save_hyperopt_logs(run_id, get_logs(run_id))
    except Exception as e:
        set_status(run_id, "failed")
        append_log(run_id, f"ERROR: {str(e)}")
        meta["status"] = "failed"
        meta["error"] = str(e)
        meta["completed_at"] = datetime.utcnow().isoformat()
        save_hyperopt_meta(run_id, meta)
        save_hyperopt_logs(run_id, get_logs(run_id))
    finally:
        remove_process(run_id)
