from pydantic import BaseModel, Field
from typing import Optional, Any


class BacktestRequest(BaseModel):
    strategy: str
    pairs: list[str]
    timeframe: str = "5m"
    timerange: Optional[str] = None
    strategy_params: dict[str, Any] = Field(default_factory=dict)


class ConfigPatchRequest(BaseModel):
    strategy: Optional[str] = None
    max_open_trades: Optional[int] = None
    dry_run_wallet: Optional[float] = None
    stake_amount: Optional[str] = None
    timeframe: Optional[str] = None


class DownloadDataRequest(BaseModel):
    pairs: list[str]
    timeframe: str = "5m"


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


class ApplyParamsRequest(BaseModel):
    strategy: str
    params: dict[str, Any]
    spaces: Optional[list[str]] = None


class DataCoverageRequest(BaseModel):
    pairs: list[str]
    timeframe: str = "5m"
