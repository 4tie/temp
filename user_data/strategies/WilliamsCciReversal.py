from functools import reduce

import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import BooleanParameter, CategoricalParameter, DecimalParameter, IntParameter

from BaseKnobStrategy import BaseKnobStrategy


class WilliamsCciReversal(BaseKnobStrategy):
    """
    Oversold-reversal strategy on the 1h timeframe.

    Requires double-oversold confirmation from both Williams %R and CCI before entering.
    A StochRSI K/D cross from the oversold zone and an EMA100 macro filter further
    reduce false entries.  The 1h timeframe smooths intraday noise while still reacting
    quickly to genuine reversals.

    Recommended pairs (range-bound large caps with deep, predictable dips):
        ADA/USDT, DOGE/USDT, LTC/USDT, ETC/USDT, ATOM/USDT
    """

    timeframe = "1h"
    startup_candle_count = 250

    minimal_roi = {
        "0": 0.08,
        "60": 0.04,
        "180": 0.02,
        "480": 0.0,
    }
    stoploss = -0.09
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    buy_willr_period = IntParameter(10, 20, default=14, space="buy", optimize=True)
    buy_willr_oversold = IntParameter(-95, -70, default=-80, space="buy", optimize=True)
    buy_cci_period = IntParameter(14, 30, default=20, space="buy", optimize=True)
    buy_cci_oversold = IntParameter(-200, -80, default=-100, space="buy", optimize=True)
    buy_stochrsi_period = IntParameter(10, 20, default=14, space="buy", optimize=True)
    buy_stochrsi_oversold = DecimalParameter(10.0, 30.0, decimals=1, default=20.0, space="buy", optimize=True)
    buy_ema_trend = IntParameter(80, 150, default=100, space="buy", optimize=True)
    buy_use_ema_filter = BooleanParameter(default=True, space="buy", optimize=True)

    sell_willr_overbought = IntParameter(-40, -10, default=-20, space="sell", optimize=True)
    sell_cci_overbought = IntParameter(80, 200, default=100, space="sell", optimize=True)
    sell_stochrsi_overbought = DecimalParameter(70.0, 90.0, decimals=1, default=80.0, space="sell", optimize=True)
    sell_exit_trigger = CategoricalParameter(["any", "two"], default="any", space="sell", optimize=True)

    protect_cooldown = IntParameter(2, 24, default=8, space="protection", optimize=True)
    protect_stop_duration = IntParameter(4, 48, default=12, space="protection", optimize=True)
    protect_stop_lookback = IntParameter(12, 96, default=24, space="protection", optimize=True)
    protect_trade_limit = IntParameter(2, 6, default=4, space="protection", optimize=True)
    protect_use_stop_guard = BooleanParameter(default=True, space="protection", optimize=True)

    @property
    def protections(self):
        return self._base_protections()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        for p in self.buy_willr_period.range:
            dataframe[f"willr_{p}"] = ta.WILLR(dataframe, timeperiod=int(p))

        for p in self.buy_cci_period.range:
            dataframe[f"cci_{p}"] = ta.CCI(dataframe, timeperiod=int(p))

        for p in self.buy_stochrsi_period.range:
            stochrsi = ta.STOCHRSI(dataframe, timeperiod=int(p), fastk_period=3, fastd_period=3)
            dataframe[f"stochrsi_k_{p}"] = stochrsi["fastk"]
            dataframe[f"stochrsi_d_{p}"] = stochrsi["fastd"]

        for val in self.buy_ema_trend.range:
            dataframe[f"ema_trend_{val}"] = ta.EMA(dataframe, timeperiod=int(val))

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        willr = dataframe[f"willr_{self.buy_willr_period.value}"]
        cci = dataframe[f"cci_{self.buy_cci_period.value}"]
        stk = dataframe[f"stochrsi_k_{self.buy_stochrsi_period.value}"]
        std = dataframe[f"stochrsi_d_{self.buy_stochrsi_period.value}"]
        ema = dataframe[f"ema_trend_{self.buy_ema_trend.value}"]

        stochrsi_cross_up = (
            (stk > std)
            & (stk.shift(1) <= std.shift(1))
            & (stk < self.buy_stochrsi_oversold.value)
        )

        conditions = [
            dataframe["volume"] > 0,
            willr < self.buy_willr_oversold.value,
            cci < self.buy_cci_oversold.value,
            stochrsi_cross_up,
        ]

        if self.buy_use_ema_filter.value:
            conditions.append(dataframe["close"] > ema)

        dataframe.loc[
            reduce(lambda x, y: x & y, conditions),
            ["enter_long", "enter_tag"],
        ] = (1, "williams_cci_oversold")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        willr = dataframe[f"willr_{self.buy_willr_period.value}"]
        cci = dataframe[f"cci_{self.buy_cci_period.value}"]
        stk = dataframe[f"stochrsi_k_{self.buy_stochrsi_period.value}"]

        cond_willr = willr > self.sell_willr_overbought.value
        cond_cci = cci > self.sell_cci_overbought.value
        cond_stoch = stk > self.sell_stochrsi_overbought.value

        if self.sell_exit_trigger.value == "two":
            exit_cond = (
                (cond_willr & cond_cci)
                | (cond_willr & cond_stoch)
                | (cond_cci & cond_stoch)
            )
        else:
            exit_cond = cond_willr | cond_cci | cond_stoch

        dataframe.loc[
            (dataframe["volume"] > 0) & exit_cond,
            ["exit_long", "exit_tag"],
        ] = (1, "williams_cci_exit")

        return dataframe
