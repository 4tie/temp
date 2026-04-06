import json
import shutil
import subprocess
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.core.config import (
    BACKTEST_RESULTS_DIR,
    DATA_DIR,
    FREQTRADE_CONFIG_FILE,
    RAW_ARTIFACT_META_SUFFIX,
    STRATEGIES_DIR,
)
from app.core.processes import (
    set_process, append_log, set_status, get_status,
    get_logs, remove_process, get_process
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


_JSON_SCALAR_TYPES = (str, int, float, bool, type(None))


def _normalized_command(default_cmd: list[str], command_override: Optional[list[str]]) -> list[str]:
    if not command_override:
        return default_cmd

    cmd = [str(token) for token in command_override]
    if not cmd:
        return default_cmd

    # If user override uses generic python launcher with -m freqtrade,
    # force the same interpreter as the app runtime.
    if (
        cmd[0].lower() in {"python", "python3"}
        and "-m" in cmd
        and "freqtrade" in cmd
        and default_cmd
    ):
        cmd[0] = default_cmd[0]

    return cmd


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


def _read_runtime_config() -> dict[str, Any]:
    if not FREQTRADE_CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(FREQTRADE_CONFIG_FILE.read_text())
    except Exception:
        return {}


def _exchange_name_from_config(cfg: dict[str, Any]) -> str | None:
    exchange = cfg.get("exchange")
    if isinstance(exchange, dict):
        return exchange.get("name")
    if isinstance(exchange, str):
        return exchange
    return None


def _ensure_valid_strategy_json(strategy: str, run_id: str, strategy_dir: Path | None = None) -> None:
    json_path = (strategy_dir or STRATEGIES_DIR) / f"{strategy}.json"
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
            json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            append_log(run_id, f"INFO: {strategy}.json migrated to nested params format.")
            return
        if "strategy_name" not in data:
            data["strategy_name"] = strategy
            json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
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
        json_path.write_text(json.dumps({"strategy_name": strategy, "params": {}}, indent=2), encoding="utf-8")
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
    exchange: Optional[str] = None,
    strategy_path: Optional[str] = None,
    strategy_label: Optional[str] = None,
    command_override: Optional[list[str]] = None,
    extra_meta: Optional[dict[str, Any]] = None,
) -> str:
    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
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

    cfg = _read_runtime_config()
    dry_run_wallet = cfg.get("dry_run_wallet")
    max_open_trades = cfg.get("max_open_trades")
    stake_amount = cfg.get("stake_amount")
    display_strategy = strategy_label or strategy
    meta: dict[str, Any] = {
        "run_id": run_id,
        "strategy": display_strategy,
        "display_strategy": display_strategy,
        "strategy_class": strategy,
        "base_strategy": strategy,
        "strategy_base": strategy,
        "pairs": pairs,
        "timeframe": timeframe,
        "timerange": timerange,
        "dry_run_wallet": dry_run_wallet,
        "max_open_trades": max_open_trades,
        "stake_amount": stake_amount,
        "exchange": exchange or _exchange_name_from_config(cfg),
        "strategy_params": strategy_params,
        "strategy_path": str(strategy_dir) if strategy_path else None,
        "command": cmd,
        "status": "running",
        "started_at": datetime.utcnow().isoformat(),
        "completed_at": None,
    }
    if extra_meta:
        meta.update(extra_meta)

    save_run_meta(run_id, meta)

    _run_subprocess(run_id, cmd, run_dir, meta)
    return run_id


def start_download(
    pairs: list[str],
    timeframe: str,
    timerange: Optional[str],
    command_override: Optional[list[str]] = None,
) -> str:
    job_id = "dl_" + datetime.utcnow().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]

    default_cmd = build_download_data_command(
        pairs=pairs,
        timeframe=timeframe,
        timerange=timerange,
    )
    cmd = _normalized_command(default_cmd, command_override)

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
    thread = threading.Thread(
        target=_backtest_worker,
        args=(run_id, cmd, run_dir, meta),
        daemon=True,
    )
    thread.start()


def _try_import_fresh_global_result(run_dir: Path, meta: dict[str, Any]) -> bool:
    """
    Import the newest global backtest artifact into this run folder only when it can be
    attributed to this run (fresh + strategy/timeframe match).
    """
    last_result_file = BACKTEST_RESULTS_DIR / ".last_result.json"
    if not last_result_file.exists():
        return False

    try:
        last_ref = json.loads(last_result_file.read_text())
    except (json.JSONDecodeError, OSError):
        return False

    latest_name = str(last_ref.get("latest_backtest") or "").strip()
    if not latest_name:
        return False

    source_artifact = BACKTEST_RESULTS_DIR / latest_name
    if not source_artifact.exists() or not source_artifact.is_file():
        return False

    # Freshness guard: artifact must be newer than this run start.
    started_at = meta.get("started_at")
    start_ts = None
    if isinstance(started_at, str) and started_at:
        try:
            start_ts = datetime.fromisoformat(started_at).timestamp()
        except ValueError:
            start_ts = None

    source_mtime = source_artifact.stat().st_mtime
    if start_ts is not None and source_mtime + 1 < start_ts:
        return False

    # Strategy/timeframe guard via companion artifact meta file when available.
    strategy_expected = str(meta.get("strategy_class") or meta.get("base_strategy") or meta.get("strategy") or "")
    timeframe_expected = str(meta.get("timeframe") or "")
    if source_artifact.suffix.lower() == ".zip":
        source_meta = source_artifact.with_name(source_artifact.name.replace(".zip", RAW_ARTIFACT_META_SUFFIX))
        if not source_meta.exists():
            return False
        try:
            meta_payload = json.loads(source_meta.read_text())
        except (json.JSONDecodeError, OSError):
            return False
        if not isinstance(meta_payload, dict) or not meta_payload:
            return False

        strategy_key = strategy_expected if strategy_expected in meta_payload else next(iter(meta_payload.keys()))
        strat_meta = meta_payload.get(strategy_key) if isinstance(meta_payload.get(strategy_key), dict) else None
        if strat_meta is None:
            return False

        if strategy_expected and strategy_expected not in meta_payload:
            return False
        if timeframe_expected and str(strat_meta.get("timeframe") or "") != timeframe_expected:
            return False

        shutil.copy2(source_meta, run_dir / source_meta.name)

    shutil.copy2(source_artifact, run_dir / source_artifact.name)
    return True


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
    command_override: Optional[list[str]] = None,
) -> str:
    run_id = "ho_" + datetime.utcnow().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
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
