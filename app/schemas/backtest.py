from pydantic import BaseModel, Field
from typing import Optional, Any


class BacktestRequest(BaseModel):
    strategy: str
    pairs: list[str]
    timeframe: str = "5m"
    timerange: Optional[str] = None
    exchange: Optional[str] = None
    strategy_path: Optional[str] = None
    strategy_label: Optional[str] = None
    strategy_params: dict[str, Any] = Field(default_factory=dict)
    command_override: Optional[list[str]] = None
    parent_run_id: Optional[str] = None
    improvement_source: Optional[str] = None
    improvement_items: list[str] = Field(default_factory=list)
    improvement_applied: list[str] = Field(default_factory=list)
    improvement_skipped: list[str] = Field(default_factory=list)
    improvement_brief: Optional[str] = None


class ConfigPatchRequest(BaseModel):
    strategy: Optional[str] = None
    max_open_trades: Optional[int] = None
    dry_run_wallet: Optional[float] = None
    stake_amount: Optional[str] = None
    timeframe: Optional[str] = None


class DownloadDataRequest(BaseModel):
    pairs: list[str]
    timeframe: str = "5m"
    timerange: Optional[str] = None
    command_override: Optional[list[str]] = None


class PresetSaveRequest(BaseModel):
    name: str
    config: dict[str, Any]


class CompareRequest(BaseModel):
    run_id_a: str
    run_id_b: str


class RunStatus(BaseModel):
    run_id: str
    status: str
    strategy: Optional[str] = None
    pairs: Optional[list[str]] = None
    timeframe: Optional[str] = None
    timerange: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    logs: list[str] = Field(default_factory=list)
    results: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class StrategyInfo(BaseModel):
    name: str
    file_path: str
    parameters: list[dict[str, Any]] = Field(default_factory=list)


class HyperoptRequest(BaseModel):
    strategy: str
    pairs: list[str]
    timeframe: str = "5m"
    timerange: Optional[str] = None
    epochs: int = 100
    spaces: list[str] = Field(default_factory=lambda: ["default"])
    loss_function: str = "SharpeHyperOptLossDaily"
    jobs: int = 1
    min_trades: int = 1
    early_stop: Optional[int] = None
    dry_run_wallet: float = 1000.0
    max_open_trades: int = 3
    stake_amount: str = "unlimited"
    random_state: Optional[int] = None
    command_override: Optional[list[str]] = None


class ApplyParamsRequest(BaseModel):
    strategy: str
    params: dict[str, Any]
    spaces: Optional[list[str]] = None


class DataCoverageRequest(BaseModel):
    pairs: list[str]
    timeframe: str = "5m"
    exchange: Optional[str] = None
    timerange: Optional[str] = None
