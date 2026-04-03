from __future__ import annotations

from functools import reduce
from pandas import DataFrame
import numpy as np
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib

from freqtrade.strategy import (
    IStrategy,
    IntParameter,
    DecimalParameter,
    CategoricalParameter,
    BooleanParameter,
)


class STRA(IStrategy):
    """
    Strategy pack: multiple entry archetypes selectable via enter_trigger.
    Works as-is on Freqtrade (interface_version=3).
    Hyperopt-ready knobs (enter/exit spaces).
    """

    interface_version = 3
    timeframe = "15m"
    process_only_new_candles = True
    startup_candle_count = 240  # needs enough candles for rolling features

    # Baseline risk controls (can be optimized via hyperopt --spaces roi/stoploss/trailing)
    minimal_roi = {"0": 0.02}
    stoploss = -0.10
    trailing_stop = False
    use_exit_signal = True

    # ===========
    # ENTER knobs
    # ===========

    enter_trigger = CategoricalParameter(
        [
            # Mean reversion
            "rsi_cross",
            "bb_rebound",
            "zscore_revert",
            # Trend / momentum
            "ema_cross",
            "macd_cross",
            "roc_momentum",
            # Breakout
            "donchian_breakout",
            "bb_squeeze_breakout",
            "keltner_breakout",
            "atr_breakout",
            # Volume + breakout
            "vol_spike_breakout",
            # Stochastic mean reversion
            "stoch_cross",
            # ADX trend confirmation
            "adx_trend_follow",
            # Range breakout simple
            "range_breakout",
        ],
        default="rsi_cross",
        space="enter",
    )

    # Guards (on/off)
    use_adx_guard = BooleanParameter(default=False, space="enter")
    adx_min = IntParameter(10, 40, default=20, space="enter")

    use_trend_guard = BooleanParameter(default=False, space="enter")
    trend_ema_period = IntParameter(50, 200, default=200, space="enter", optimize=False)

    # RSI
    rsi_period = IntParameter(7, 30, default=14, space="enter", optimize=False)
    rsi_buy = IntParameter(10, 40, default=30, space="enter")

    # EMA cross / Trend
    ema_fast_period = IntParameter(5, 50, default=12, space="enter", optimize=False)
    ema_slow_period = IntParameter(20, 200, default=26, space="enter", optimize=False)

    # MACD
    macd_fast = IntParameter(8, 20, default=12, space="enter", optimize=False)
    macd_slow = IntParameter(18, 40, default=26, space="enter", optimize=False)
    macd_signal = IntParameter(5, 15, default=9, space="enter", optimize=False)

    # Bollinger
    bb_period = IntParameter(10, 40, default=20, space="enter", optimize=False)
    bb_dev = DecimalParameter(1.0, 3.0, default=2.0, decimals=1, space="enter")

    bb_width_max = DecimalParameter(0.01, 0.20, default=0.06, decimals=3, space="enter")  # for squeeze

    # Donchian (breakout)
    donchian_period = IntParameter(10, 80, default=20, space="enter")

    # ATR breakout / Keltner
    atr_period = IntParameter(7, 50, default=14, space="enter", optimize=False)
    atr_mult_breakout = DecimalParameter(0.5, 5.0, default=1.5, decimals=2, space="enter")
    atr_mult_keltner = DecimalParameter(0.5, 4.0, default=1.5, decimals=2, space="enter")

    # Stoch
    stoch_k_period = IntParameter(5, 30, default=14, space="enter", optimize=False)
    stoch_d_period = IntParameter(3, 10, default=3, space="enter", optimize=False)
    stoch_buy = IntParameter(5, 30, default=20, space="enter")

    # Zscore mean reversion
    z_period = IntParameter(20, 200, default=50, space="enter", optimize=False)
    z_buy = DecimalParameter(-3.0, -0.5, default=-1.5, decimals=2, space="enter")

    # Momentum (ROC)
    roc_period = IntParameter(5, 50, default=10, space="enter", optimize=False)
    roc_min = DecimalParameter(0.5, 10.0, default=2.0, decimals=2, space="enter")

    # Volume breakout
    vol_sma_period = IntParameter(10, 100, default=30, space="enter", optimize=False)
    vol_mult = DecimalParameter(1.0, 6.0, default=2.0, decimals=2, space="enter")

    # Range breakout
    range_period = IntParameter(10, 80, default=20, space="enter")
    range_breakout_pct = DecimalParameter(0.001, 0.05, default=0.01, decimals=3, space="enter")

    # ==========
    # EXIT knobs
    # ==========

    exit_trigger = CategoricalParameter(
        ["none", "rsi_tp", "ema_cross_down", "macd_cross_down", "bb_mid", "atr_flip"],
        default="rsi_tp",
        space="exit",
    )

    rsi_sell = IntParameter(50, 90, default=70, space="exit")
    atr_mult_exit = DecimalParameter(0.5, 5.0, default=2.0, decimals=2, space="exit")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Core safety
        dataframe["volume"] = dataframe["volume"].fillna(0.0)

        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=int(self.rsi_period.value))

        # EMA
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=int(self.ema_fast_period.value))
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=int(self.ema_slow_period.value))
        dataframe["ema_trend"] = ta.EMA(dataframe, timeperiod=int(self.trend_ema_period.value))

        # MACD
        macd = ta.MACD(
            dataframe,
            fastperiod=int(self.macd_fast.value),
            slowperiod=int(self.macd_slow.value),
            signalperiod=int(self.macd_signal.value),
        )
        dataframe["macd"] = macd["macd"]
        dataframe["macdsignal"] = macd["macdsignal"]

        # ADX
        dataframe["adx"] = ta.ADX(dataframe)

        # Bollinger
        bb = ta.BBANDS(
            dataframe,
            timeperiod=int(self.bb_period.value),
            nbdevup=float(self.bb_dev.value),
            nbdevdn=float(self.bb_dev.value),
        )
        dataframe["bb_lower"] = bb["lowerband"]
        dataframe["bb_mid"] = bb["middleband"]
        dataframe["bb_upper"] = bb["upperband"]
        dataframe["bb_width"] = (dataframe["bb_upper"] - dataframe["bb_lower"]) / dataframe["bb_mid"].replace(0, np.nan)

        # Donchian
        p = int(self.donchian_period.value)
        dataframe["donch_high"] = dataframe["high"].rolling(p).max()
        dataframe["donch_low"] = dataframe["low"].rolling(p).min()

        # ATR + Keltner
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=int(self.atr_period.value))
        kc_mid = dataframe["ema_slow"]
        dataframe["kc_upper"] = kc_mid + float(self.atr_mult_keltner.value) * dataframe["atr"]
        dataframe["kc_lower"] = kc_mid - float(self.atr_mult_keltner.value) * dataframe["atr"]

        # Stochastic
        stoch = ta.STOCH(
            dataframe,
            fastk_period=int(self.stoch_k_period.value),
            slowk_period=3,
            slowk_matype=0,
            slowd_period=int(self.stoch_d_period.value),
            slowd_matype=0,
        )
        dataframe["stoch_k"] = stoch["slowk"]
        dataframe["stoch_d"] = stoch["slowd"]

        # Zscore
        zp = int(self.z_period.value)
        mean = dataframe["close"].rolling(zp).mean()
        std = dataframe["close"].rolling(zp).std().replace(0, np.nan)
        dataframe["zscore"] = (dataframe["close"] - mean) / std

        # ROC (momentum)
        dataframe["roc"] = ta.ROC(dataframe, timeperiod=int(self.roc_period.value))

        # Volume SMA
        dataframe["vol_sma"] = dataframe["volume"].rolling(int(self.vol_sma_period.value)).mean()

        # Range
        rp = int(self.range_period.value)
        dataframe["range_high"] = dataframe["high"].rolling(rp).max()
        dataframe["range_low"] = dataframe["low"].rolling(rp).min()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []

        # Always require real candles
        conditions.append(dataframe["volume"] > 0)

        # Optional guards
        if self.use_adx_guard.value:
            conditions.append(dataframe["adx"] > int(self.adx_min.value))

        if self.use_trend_guard.value:
            conditions.append(dataframe["close"] > dataframe["ema_trend"])

        trig = self.enter_trigger.value

        if trig == "rsi_cross":
            conditions.append(qtpylib.crossed_above(dataframe["rsi"], int(self.rsi_buy.value)))

        elif trig == "ema_cross":
            conditions.append(qtpylib.crossed_above(dataframe["ema_fast"], dataframe["ema_slow"]))

        elif trig == "macd_cross":
            conditions.append(qtpylib.crossed_above(dataframe["macd"], dataframe["macdsignal"]))

        elif trig == "bb_rebound":
            conditions.append(qtpylib.crossed_above(dataframe["close"], dataframe["bb_lower"]))

        elif trig == "donchian_breakout":
            # break above previous donchian high
            conditions.append(dataframe["close"] > dataframe["donch_high"].shift(1))

        elif trig == "bb_squeeze_breakout":
            conditions.append(dataframe["bb_width"] < float(self.bb_width_max.value))
            conditions.append(qtpylib.crossed_above(dataframe["close"], dataframe["bb_upper"]))

        elif trig == "keltner_breakout":
            conditions.append(qtpylib.crossed_above(dataframe["close"], dataframe["kc_upper"]))

        elif trig == "atr_breakout":
            conditions.append(
                dataframe["close"] > dataframe["close"].shift(1) + float(self.atr_mult_breakout.value) * dataframe["atr"]
            )

        elif trig == "vol_spike_breakout":
            conditions.append(dataframe["volume"] > float(self.vol_mult.value) * dataframe["vol_sma"])
            conditions.append(dataframe["close"] > dataframe["donch_high"].shift(1))

        elif trig == "stoch_cross":
            conditions.append(qtpylib.crossed_above(dataframe["stoch_k"], dataframe["stoch_d"]))
            conditions.append(dataframe["stoch_k"] < int(self.stoch_buy.value))

        elif trig == "zscore_revert":
            # buy when zscore recovers above a negative threshold (mean reversion signal)
            conditions.append(qtpylib.crossed_above(dataframe["zscore"], float(self.z_buy.value)))

        elif trig == "roc_momentum":
            conditions.append(dataframe["roc"] > float(self.roc_min.value))

        elif trig == "adx_trend_follow":
            conditions.append(dataframe["adx"] > int(self.adx_min.value))
            conditions.append(dataframe["close"] > dataframe["ema_slow"])
            conditions.append(dataframe["ema_fast"] > dataframe["ema_slow"])

        elif trig == "range_breakout":
            # close breaks above range high by pct
            pct = float(self.range_breakout_pct.value)
            conditions.append(dataframe["close"] > dataframe["range_high"].shift(1) * (1.0 + pct))

        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                ["enter_long", "enter_tag"],
            ] = (1, f"{trig}")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        conditions.append(dataframe["volume"] > 0)

        trig = self.exit_trigger.value

        if trig == "none":
            return dataframe

        if trig == "rsi_tp":
            conditions.append(qtpylib.crossed_above(dataframe["rsi"], int(self.rsi_sell.value)))

        elif trig == "ema_cross_down":
            conditions.append(qtpylib.crossed_below(dataframe["ema_fast"], dataframe["ema_slow"]))

        elif trig == "macd_cross_down":
            conditions.append(qtpylib.crossed_below(dataframe["macd"], dataframe["macdsignal"]))

        elif trig == "bb_mid":
            conditions.append(qtpylib.crossed_above(dataframe["close"], dataframe["bb_mid"]))

        elif trig == "atr_flip":
            # volatility-based exit: close drops below (ema_fast - atr_mult_exit * atr)
            conditions.append(
                dataframe["close"] < (dataframe["ema_fast"] - float(self.atr_mult_exit.value) * dataframe["atr"])
            )

        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                ["exit_long", "exit_tag"],
            ] = (1, f"{trig}")

        return dataframe