from functools import reduce

import freqtrade.vendor.qtpylib.indicators as qtpylib
import talib.abstract as ta
from pandas import DataFrame

from BaseKnobStrategy import BaseKnobStrategy


class SessionScalp5mBase(BaseKnobStrategy):
    """
    5m trend-pullback scalper with a local-session entry gate.
    The timezone subclasses below keep the same local trading window
    while shifting which UTC candles are tradable.
    """

    minimal_roi = {
        "0": 0.08,
        "30": 0.04,
        "90": 0.02,
        "240": 0.0,
    }
    stoploss = -0.09
    trailing_stop = False
    trailing_stop_positive = None
    trailing_stop_positive_offset = 0.0
    trailing_only_offset_is_reached = False
    startup_candle_count = 220

    session_timezone = "UTC"
    session_start_hour = 8
    session_end_hour = 22

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
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)

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
            dataframe["adx"] > 22,
            dataframe["rsi"] > 52,
            dataframe["ema_fast"] > dataframe["ema_slow"],
            dataframe["close"] > dataframe["ema_slow"],
            dataframe["close"] <= dataframe["ema_fast"] * 0.995,
        ]

        dataframe.loc[
            reduce(lambda x, y: x & y, conditions),
            ["enter_long", "enter_tag"],
        ] = (1, "session_scalp_entry")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_condition = (
            qtpylib.crossed_below(dataframe["ema_fast"], dataframe["ema_slow"])
            | (dataframe["rsi"] > 70)
        )

        dataframe.loc[
            (dataframe["volume"] > 0) & exit_condition,
            ["exit_long", "exit_tag"],
        ] = (1, "session_scalp_exit")

        return dataframe


class SessionScalp5m(SessionScalp5mBase):
    pass


class SessionScalp5mUTC(SessionScalp5mBase):
    session_timezone = "UTC"


class SessionScalp5mRiyadh(SessionScalp5mBase):
    session_timezone = "Asia/Riyadh"


class SessionScalp5mLondon(SessionScalp5mBase):
    session_timezone = "Europe/London"


class SessionScalp5mNewYork(SessionScalp5mBase):
    session_timezone = "America/New_York"
