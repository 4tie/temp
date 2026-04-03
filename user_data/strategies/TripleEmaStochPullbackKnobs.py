from functools import reduce

import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import BooleanParameter, DecimalParameter, IntParameter

from BaseKnobStrategy import BaseKnobStrategy


class TripleEmaStochPullbackKnobs(BaseKnobStrategy):
    """
    Pullback strategy that buys in an existing uptrend using EMA structure,
    Stochastic recovery, and RSI pullback confirmation.
    """

    minimal_roi = {
        "0": 0.07,
        "45": 0.035,
        "120": 0.015,
        "300": 0.0,
    }
    stoploss = -0.08
    startup_candle_count = 250

    buy_fast_ema = IntParameter(5, 15, default=9, space="buy", optimize=True)
    buy_mid_ema = IntParameter(20, 50, default=21, space="buy", optimize=True)
    buy_rsi = IntParameter(20, 45, default=34, space="buy", optimize=True)
    buy_stoch = IntParameter(8, 35, default=20, space="buy", optimize=True)
    buy_pullback = DecimalParameter(0.975, 1.000, decimals=3, default=0.992, space="buy", optimize=True)
    buy_require_ema200 = BooleanParameter(default=True, space="buy", optimize=True)

    sell_rsi = IntParameter(50, 80, default=62, space="sell", optimize=True)
    sell_stoch = IntParameter(60, 95, default=80, space="sell", optimize=True)

    protect_cooldown = IntParameter(2, 24, default=6, space="protection", optimize=True)
    protect_stop_duration = IntParameter(4, 48, default=10, space="protection", optimize=True)
    protect_stop_lookback = IntParameter(12, 96, default=24, space="protection", optimize=True)
    protect_trade_limit = IntParameter(2, 6, default=4, space="protection", optimize=True)
    protect_use_stop_guard = BooleanParameter(default=True, space="protection", optimize=True)

    @property
    def protections(self):
        return self._base_protections()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)

        stoch = ta.STOCH(dataframe)
        dataframe["stoch_k"] = stoch["slowk"]
        dataframe["stoch_d"] = stoch["slowd"]

        for val in self.buy_fast_ema.range:
            dataframe[f"ema_fast_{val}"] = ta.EMA(dataframe, timeperiod=int(val))

        for val in self.buy_mid_ema.range:
            dataframe[f"ema_mid_{val}"] = ta.EMA(dataframe, timeperiod=int(val))

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        fast = dataframe[f"ema_fast_{self.buy_fast_ema.value}"]
        mid = dataframe[f"ema_mid_{self.buy_mid_ema.value}"]

        conditions = [
            dataframe["volume"] > 0,
            fast > mid,
            dataframe["close"] <= fast * self.buy_pullback.value,
            dataframe["rsi"] < self.buy_rsi.value,
            dataframe["stoch_k"] < self.buy_stoch.value,
            dataframe["stoch_k"] > dataframe["stoch_d"],
        ]

        if self.buy_require_ema200.value:
            conditions.append(dataframe["close"] > dataframe["ema200"])
            conditions.append(mid > dataframe["ema200"])

        dataframe.loc[
            reduce(lambda x, y: x & y, conditions),
            ["enter_long", "enter_tag"],
        ] = (1, "ema_pullback")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        mid = dataframe[f"ema_mid_{self.buy_mid_ema.value}"]

        dataframe.loc[
            (dataframe["volume"] > 0)
            & (
                (dataframe["close"] < mid)
                | (dataframe["rsi"] > self.sell_rsi.value)
                | (dataframe["stoch_k"] > self.sell_stoch.value)
            ),
            ["exit_long", "exit_tag"],
        ] = (1, "pullback_exit")

        return dataframe
