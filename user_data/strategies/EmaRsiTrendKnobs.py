from functools import reduce

import talib.abstract as ta
from pandas import DataFrame
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import BooleanParameter, CategoricalParameter, DecimalParameter, IntParameter

from BaseKnobStrategy import BaseKnobStrategy


class EmaRsiTrendKnobs(BaseKnobStrategy):
    """
    Trend-following EMA strategy with tunable EMA periods, RSI floor, ADX filter,
    optional pullback trigger, and tunable protections.
    """

    minimal_roi = {
        "0": 0.08,
        "30": 0.04,
        "90": 0.02,
        "240": 0.0,
    }
    stoploss = -0.09
    startup_candle_count = 220

    buy_fast_ema = IntParameter(5, 20, default=9, space="buy", optimize=True)
    buy_slow_ema = IntParameter(21, 80, default=50, space="buy", optimize=True)
    buy_rsi_floor = IntParameter(45, 65, default=52, space="buy", optimize=True)
    buy_adx = DecimalParameter(15.0, 35.0, decimals=1, default=22.0, space="buy", optimize=True)
    buy_pullback = DecimalParameter(0.975, 1.005, decimals=3, default=0.995, space="buy", optimize=True)
    buy_trigger = CategoricalParameter(["cross", "pullback"], default="pullback", space="buy", optimize=True)

    sell_rsi = IntParameter(55, 85, default=70, space="sell", optimize=True)
    sell_cross_under = BooleanParameter(default=True, space="sell", optimize=True)

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
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)

        for val in self.buy_fast_ema.range:
            dataframe[f"ema_fast_{val}"] = ta.EMA(dataframe, timeperiod=int(val))

        for val in self.buy_slow_ema.range:
            dataframe[f"ema_slow_{val}"] = ta.EMA(dataframe, timeperiod=int(val))

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        fast = dataframe[f"ema_fast_{self.buy_fast_ema.value}"]
        slow = dataframe[f"ema_slow_{self.buy_slow_ema.value}"]

        conditions = [
            dataframe["volume"] > 0,
            dataframe["rsi"] > self.buy_rsi_floor.value,
            dataframe["adx"] > self.buy_adx.value,
            fast > slow,
            dataframe["close"] > slow,
        ]

        if self.buy_trigger.value == "cross":
            conditions.append(qtpylib.crossed_above(fast, slow))
        else:
            conditions.append(dataframe["close"] <= fast * self.buy_pullback.value)

        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                ["enter_long", "enter_tag"],
            ] = (1, f"ema_{self.buy_trigger.value}")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        fast = dataframe[f"ema_fast_{self.buy_fast_ema.value}"]
        slow = dataframe[f"ema_slow_{self.buy_slow_ema.value}"]

        exit_condition = dataframe["rsi"] > self.sell_rsi.value
        if self.sell_cross_under.value:
            exit_condition = exit_condition | qtpylib.crossed_below(fast, slow)

        dataframe.loc[
            (dataframe["volume"] > 0) & exit_condition,
            ["exit_long", "exit_tag"],
        ] = (1, "ema_exit")

        return dataframe
