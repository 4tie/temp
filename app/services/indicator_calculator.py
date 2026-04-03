import re
from typing import Optional

import numpy as np

from app.services.ohlcv_loader import load_ohlcv


def _sma(values: np.ndarray, period: int) -> list:
    if len(values) < period:
        return [None] * len(values)
    result = [None] * (period - 1)
    cumsum = np.cumsum(values)
    sma_vals = (cumsum[period - 1:] - np.concatenate([[0], cumsum[:-period]])) / period
    result.extend(sma_vals.tolist())
    return result


def _ema(values: np.ndarray, period: int) -> list:
    if len(values) < period:
        return [None] * len(values)
    result = [None] * (period - 1)
    multiplier = 2.0 / (period + 1)
    ema_val = float(np.mean(values[:period]))
    result.append(ema_val)
    for i in range(period, len(values)):
        ema_val = (values[i] - ema_val) * multiplier + ema_val
        result.append(ema_val)
    return result


def _rsi(values: np.ndarray, period: int) -> list:
    if len(values) < period + 1:
        return [None] * len(values)

    deltas = np.diff(values)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = float(np.mean(gains[:period]))
    avg_loss = float(np.mean(losses[:period]))

    result = [None] * period
    if avg_loss == 0:
        result.append(100.0)
    else:
        rs = avg_gain / avg_loss
        result.append(100.0 - 100.0 / (1.0 + rs))

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            result.append(100.0)
        else:
            rs = avg_gain / avg_loss
            result.append(100.0 - 100.0 / (1.0 + rs))

    return result


def _macd(
    values: np.ndarray,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict:
    ema_fast = _ema(values, fast)
    ema_slow = _ema(values, slow)

    macd_line = []
    for f, s in zip(ema_fast, ema_slow):
        if f is None or s is None:
            macd_line.append(None)
        else:
            macd_line.append(f - s)

    valid_macd = [v for v in macd_line if v is not None]
    if len(valid_macd) >= signal:
        signal_line_raw = _ema(np.array(valid_macd), signal)
        none_count = len(macd_line) - len(valid_macd)
        signal_line = [None] * none_count + signal_line_raw
    else:
        signal_line = [None] * len(macd_line)

    histogram = []
    for m, s_val in zip(macd_line, signal_line):
        if m is None or s_val is None:
            histogram.append(None)
        else:
            histogram.append(m - s_val)

    return {
        "macd": macd_line,
        "macd_signal": signal_line,
        "macd_histogram": histogram,
    }


def _bbands(values: np.ndarray, period: int, std_dev: float = 2.0) -> dict:
    sma = _sma(values, period)

    upper = []
    lower = []
    for i in range(len(values)):
        if sma[i] is None:
            upper.append(None)
            lower.append(None)
        else:
            window = values[max(0, i - period + 1): i + 1]
            sd = float(np.std(window, ddof=0))
            upper.append(sma[i] + std_dev * sd)
            lower.append(sma[i] - std_dev * sd)

    return {
        "bbands_upper": upper,
        "bbands_middle": sma,
        "bbands_lower": lower,
    }


def _vwap(ohlcv: list[dict]) -> list:
    result = []
    cum_vol = 0.0
    cum_tp_vol = 0.0
    for candle in ohlcv:
        tp = (candle["high"] + candle["low"] + candle["close"]) / 3.0
        vol = candle["volume"]
        cum_vol += vol
        cum_tp_vol += tp * vol
        if cum_vol == 0:
            result.append(None)
        else:
            result.append(cum_tp_vol / cum_vol)
    return result


def _stochastic(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    k_period: int = 14,
    d_period: int = 3,
) -> dict:
    k_values: list = []
    for i in range(len(closes)):
        if i < k_period - 1:
            k_values.append(None)
            continue
        window_high = float(np.max(highs[i - k_period + 1: i + 1]))
        window_low = float(np.min(lows[i - k_period + 1: i + 1]))
        if window_high == window_low:
            k_values.append(50.0)
        else:
            k_values.append(((closes[i] - window_low) / (window_high - window_low)) * 100.0)

    valid_k = [v for v in k_values if v is not None]
    if len(valid_k) >= d_period:
        d_raw = _sma(np.array(valid_k), d_period)
        none_count = len(k_values) - len(valid_k)
        d_values = [None] * none_count + d_raw
    else:
        d_values = [None] * len(k_values)

    return {
        "stoch_k": k_values,
        "stoch_d": d_values,
    }


_INDICATOR_PATTERN = re.compile(r"^([a-z]+)(?:_(\d+))?(?:_(\d+))?(?:_(\d+))?$")


def _parse_indicator_spec(spec: str) -> tuple[str, list[int]]:
    m = _INDICATOR_PATTERN.match(spec.lower().strip())
    if not m:
        return spec.lower().strip(), []
    name = m.group(1)
    params = []
    for i in range(2, 5):
        if m.group(i) is not None:
            val = int(m.group(i))
            if val < 0 or val > 1000:
                val = 0
            params.append(val)
    return name, params


_DEFAULT_PERIODS = {
    "sma": 20,
    "ema": 50,
    "rsi": 14,
    "bbands": 20,
    "stoch": 14,
}


def calculate_indicators(
    pair: str,
    timeframe: str,
    exchange: str,
    indicators: list[str],
    timerange: Optional[str] = None,
) -> dict:
    ohlcv = load_ohlcv(pair, timeframe, exchange, timerange)
    if not ohlcv:
        return {"dates": [], "indicators": {}}

    dates = [c["date"] for c in ohlcv]
    closes = np.array([c["close"] for c in ohlcv], dtype=np.float64)
    highs = np.array([c["high"] for c in ohlcv], dtype=np.float64)
    lows = np.array([c["low"] for c in ohlcv], dtype=np.float64)

    result: dict = {}

    for spec in indicators:
        name, params = _parse_indicator_spec(spec)

        if name == "sma":
            p = params[0] if params else _DEFAULT_PERIODS["sma"]
            result[f"sma_{p}"] = _sma(closes, p)

        elif name == "ema":
            p = params[0] if params else _DEFAULT_PERIODS["ema"]
            result[f"ema_{p}"] = _ema(closes, p)

        elif name == "rsi":
            p = params[0] if params else _DEFAULT_PERIODS["rsi"]
            result[f"rsi_{p}"] = _rsi(closes, p)

        elif name == "macd":
            fast = params[0] if len(params) > 0 else 12
            slow = params[1] if len(params) > 1 else 26
            signal = params[2] if len(params) > 2 else 9
            macd_data = _macd(closes, fast, slow, signal)
            result[f"macd_{fast}_{slow}_{signal}"] = macd_data["macd"]
            result[f"macd_signal_{fast}_{slow}_{signal}"] = macd_data["macd_signal"]
            result[f"macd_histogram_{fast}_{slow}_{signal}"] = macd_data["macd_histogram"]

        elif name == "bbands":
            p = params[0] if params else _DEFAULT_PERIODS["bbands"]
            bb_data = _bbands(closes, p)
            result[f"bbands_upper_{p}"] = bb_data["bbands_upper"]
            result[f"bbands_middle_{p}"] = bb_data["bbands_middle"]
            result[f"bbands_lower_{p}"] = bb_data["bbands_lower"]

        elif name == "vwap":
            result["vwap"] = _vwap(ohlcv)

        elif name == "stoch":
            p = params[0] if params else _DEFAULT_PERIODS["stoch"]
            stoch_data = _stochastic(highs, lows, closes, p)
            result[f"stoch_k_{p}"] = stoch_data["stoch_k"]
            result[f"stoch_d_{p}"] = stoch_data["stoch_d"]

    return {"dates": dates, "indicators": result}
