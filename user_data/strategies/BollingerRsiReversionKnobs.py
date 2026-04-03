from functools import reduce

import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import BooleanParameter, CategoricalParameter, IntParameter

from BaseKnobStrategy import BaseKnobStrategy


class BollingerRsiReversionKnobs(BaseKnobStrategy):
    """
    Mean-reversion strategy using Bollinger Bands, RSI, MFI, and an optional EMA200 trend filter.
    """

    minimal_roi = {
        "0": 0.06,
        "45": 0.03,
        "120": 0.015,
        "300": 0.0,
    }
    stoploss = -0.12
    startup_candle_count = 250

    buy_bb_window = IntParameter(16, 30, default=20, space="buy", optimize=True)
    buy_bb_std = CategoricalParameter([1.8, 2.0, 2.2, 2.5], default=2.0, space="buy", optimize=True)
    buy_rsi = IntParameter(18, 40, default=30, space="buy", optimize=True)
    buy_mfi = IntParameter(10, 40, default=24, space="buy", optimize=True)
    buy_use_trend_filter = BooleanParameter(default=True, space="buy", optimize=True)

    sell_rsi = IntParameter(50, 80, default=60, space="sell", optimize=True)
    sell_band = CategoricalParameter(["mid", "upper"], default="mid", space="sell", optimize=True)

    protect_cooldown = IntParameter(2, 24, default=6, space="protection", optimize=True)
    protect_stop_duration = IntParameter(4, 48, default=10, space="protection", optimize=True)
    protect_stop_lookback = IntParameter(12, 96, default=24, space="protection", optimize=True)
    protect_trade_limit = IntParameter(2, 6, default=4, space="protection", optimize=True)
    protect_use_stop_guard = BooleanParameter(default=True, space="protection", optimize=True)

    @property
    def protections(self):
        return self._base_protections()

    @staticmethod
    def _bb_suffix(std_value: float) -> str:
        return str(std_value).replace(".", "_")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["mfi"] = ta.MFI(dataframe, timeperiod=14)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)

        for window in self.buy_bb_window.range:
            mid = dataframe["close"].rolling(int(window)).mean()
            std = dataframe["close"].rolling(int(window)).std(ddof=0)
            dataframe[f"bb_mid_{window}"] = mid
            for stdv in self.buy_bb_std.range:
                suffix = self._bb_suffix(stdv)
                dataframe[f"bb_lower_{window}_{suffix}"] = mid - (std * float(stdv))
                dataframe[f"bb_upper_{window}_{suffix}"] = mid + (std * float(stdv))

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        window = self.buy_bb_window.value
        suffix = self._bb_suffix(self.buy_bb_std.value)
        lower = dataframe[f"bb_lower_{window}_{suffix}"]

        conditions = [
            dataframe["volume"] > 0,
            dataframe["close"] < lower,
            dataframe["rsi"] < self.buy_rsi.value,
            dataframe["mfi"] < self.buy_mfi.value,
        ]

        if self.buy_use_trend_filter.value:
            conditions.append(dataframe["close"] > dataframe["ema200"])

        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                ["enter_long", "enter_tag"],
            ] = (1, "bb_reversion")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        window = self.buy_bb_window.value
        suffix = self._bb_suffix(self.buy_bb_std.value)
        mid = dataframe[f"bb_mid_{window}"]
        upper = dataframe[f"bb_upper_{window}_{suffix}"]
        exit_band = upper if self.sell_band.value == "upper" else mid

        dataframe.loc[
            (dataframe["volume"] > 0)
            & ((dataframe["close"] > exit_band) | (dataframe["rsi"] > self.sell_rsi.value)),
            ["exit_long", "exit_tag"],
        ] = (1, f"bb_{self.sell_band.value}_exit")

        return dataframe
