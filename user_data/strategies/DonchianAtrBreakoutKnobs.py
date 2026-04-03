from functools import reduce

import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import BooleanParameter, CategoricalParameter, DecimalParameter, IntParameter

from BaseKnobStrategy import BaseKnobStrategy


class DonchianAtrBreakoutKnobs(BaseKnobStrategy):
    """
    Breakout strategy using Donchian channels, ATR activity filter, and RSI confirmation.
    """

    minimal_roi = {
        "0": 0.12,
        "60": 0.06,
        "180": 0.03,
        "480": 0.0,
    }
    stoploss = -0.11
    startup_candle_count = 220

    buy_dc_period = IntParameter(10, 40, default=20, space="buy", optimize=True)
    buy_atr_pct = DecimalParameter(0.3, 3.0, decimals=1, default=0.8, space="buy", optimize=True)
    buy_rsi = IntParameter(45, 70, default=55, space="buy", optimize=True)
    buy_use_ema_filter = BooleanParameter(default=False, space="buy", optimize=True)

    sell_exit_channel = CategoricalParameter(["mid", "lower"], default="mid", space="sell", optimize=True)
    sell_rsi = IntParameter(30, 55, default=42, space="sell", optimize=True)

    protect_cooldown = IntParameter(2, 24, default=8, space="protection", optimize=True)
    protect_stop_duration = IntParameter(4, 48, default=12, space="protection", optimize=True)
    protect_stop_lookback = IntParameter(12, 96, default=24, space="protection", optimize=True)
    protect_trade_limit = IntParameter(2, 6, default=4, space="protection", optimize=True)
    protect_use_stop_guard = BooleanParameter(default=True, space="protection", optimize=True)

    @property
    def protections(self):
        return self._base_protections()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = (dataframe["atr"] / dataframe["close"]) * 100.0
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)

        for period in self.buy_dc_period.range:
            period = int(period)
            dataframe[f"dc_upper_{period}"] = dataframe["high"].rolling(period).max().shift(1)
            dataframe[f"dc_lower_{period}"] = dataframe["low"].rolling(period).min().shift(1)
            dataframe[f"dc_mid_{period}"] = (
                dataframe[f"dc_upper_{period}"] + dataframe[f"dc_lower_{period}"]
            ) / 2.0

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        period = int(self.buy_dc_period.value)
        upper = dataframe[f"dc_upper_{period}"]

        conditions = [
            dataframe["volume"] > 0,
            dataframe["close"] > upper,
            dataframe["atr_pct"] > self.buy_atr_pct.value,
            dataframe["rsi"] > self.buy_rsi.value,
        ]

        if self.buy_use_ema_filter.value:
            conditions.append(dataframe["close"] > dataframe["ema200"])

        dataframe.loc[
            reduce(lambda x, y: x & y, conditions),
            ["enter_long", "enter_tag"],
        ] = (1, "donchian_breakout")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        period = int(self.buy_dc_period.value)
        exit_line = dataframe[f"dc_mid_{period}"]
        if self.sell_exit_channel.value == "lower":
            exit_line = dataframe[f"dc_lower_{period}"]

        dataframe.loc[
            (dataframe["volume"] > 0)
            & ((dataframe["close"] < exit_line) | (dataframe["rsi"] < self.sell_rsi.value)),
            ["exit_long", "exit_tag"],
        ] = (1, f"dc_{self.sell_exit_channel.value}_exit")

        return dataframe
