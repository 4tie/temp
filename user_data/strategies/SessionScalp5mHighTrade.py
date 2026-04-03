from functools import reduce

import freqtrade.vendor.qtpylib.indicators as qtpylib
import talib.abstract as ta
from pandas import DataFrame

from BaseKnobStrategy import BaseKnobStrategy


class SessionScalp5mHighTradeBase(BaseKnobStrategy):
    """
    Higher-activity 5m session scalper.
    This is intentionally more aggressive than SessionScalp5m and is expected
    to trade far more often, at the cost of weaker quality.
    """

    minimal_roi = {
        "0": 0.018,
        "20": 0.009,
        "60": 0.0,
    }
    stoploss = -0.03
    trailing_stop = True
    trailing_stop_positive = 0.004
    trailing_stop_positive_offset = 0.008
    trailing_only_offset_is_reached = True
    startup_candle_count = 240

    session_timezone = "UTC"
    session_start_hour = 6
    session_end_hour = 23

    @staticmethod
    def _local_session_mask(
        dataframe: DataFrame,
        timezone_name: str,
        session_start_hour: int,
        session_end_hour: int,
    ):
        date_series = dataframe["date"]
        if date_series.dt.tz is None:
            localized = date_series.dt.tz_localize("UTC")
        else:
            localized = date_series.dt.tz_convert("UTC")

        local_hour = localized.dt.tz_convert(timezone_name).dt.hour
        if session_start_hour < session_end_hour:
            return (local_hour >= session_start_hour) & (local_hour < session_end_hour)

        return (local_hour >= session_start_hour) | (local_hour < session_end_hour)

    @property
    def protections(self):
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=9)
        dataframe["ema_mid"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema_trend"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["mfi"] = ta.MFI(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]

        stoch = ta.STOCH(dataframe, fastk_period=14, slowk_period=3, slowd_period=3)
        dataframe["stoch_k"] = stoch["slowk"]
        dataframe["stoch_d"] = stoch["slowd"]

        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=18, stds=2.0)
        dataframe["bb_mid"] = bollinger["mid"]
        dataframe["bb_upper"] = bollinger["upper"]
        dataframe["bb_lower"] = bollinger["lower"]

        dataframe["session_allowed"] = self._local_session_mask(
            dataframe,
            self.session_timezone,
            self.session_start_hour,
            self.session_end_hour,
        ).astype("int8")

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = [
            dataframe["volume"] > 0,
            dataframe["session_allowed"] == 1,
            dataframe["ema_mid"] > dataframe["ema_trend"] * 0.997,
            dataframe["close"] > dataframe["ema_trend"] * 0.994,
            dataframe["close"] < dataframe["bb_lower"] * 1.003,
            dataframe["close"] < dataframe["ema_mid"] * 0.998,
            dataframe["rsi"] > 24,
            dataframe["rsi"] < 42,
            dataframe["mfi"] < 38,
            dataframe["stoch_k"] < 42,
            dataframe["stoch_k"] > dataframe["stoch_d"],
            dataframe["atr_pct"] > 0.0012,
        ]

        dataframe.loc[
            reduce(lambda x, y: x & y, conditions),
            ["enter_long", "enter_tag"],
        ] = (1, "session_scalp_hightrade_entry")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_condition = (
            (dataframe["close"] >= dataframe["bb_mid"])
            | (dataframe["rsi"] > 56)
            | (dataframe["stoch_k"] > 74)
            | ((dataframe["close"] < dataframe["ema_slow"]) & (dataframe["rsi"] < 40))
        )

        dataframe.loc[
            (dataframe["volume"] > 0) & exit_condition,
            ["exit_long", "exit_tag"],
        ] = (1, "session_scalp_hightrade_exit")

        return dataframe


class SessionScalp5mHighTradeUTC(SessionScalp5mHighTradeBase):
    session_timezone = "UTC"


class SessionScalp5mHighTradeRiyadh(SessionScalp5mHighTradeBase):
    session_timezone = "Asia/Riyadh"


class SessionScalp5mHighTradeLondon(SessionScalp5mHighTradeBase):
    session_timezone = "Europe/London"


class SessionScalp5mHighTradeNewYork(SessionScalp5mHighTradeBase):
    session_timezone = "America/New_York"


class SessionScalp5mHighTrade(SessionScalp5mHighTradeUTC):
    """
    Default preset exposed under the pack filename for app-driven backtests.
    """

    pass
