from functools import reduce

import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import BooleanParameter, CategoricalParameter, DecimalParameter, IntParameter

from BaseKnobStrategy import BaseKnobStrategy


class IchimokuTrendRider(BaseKnobStrategy):
    """
    Ichimoku Cloud trend-following strategy on the 4h timeframe.

    All five Ichimoku components must agree before a trade is opened: price above a
    green (bullish) cloud, Tenkan above Kijun, Chikou Span above the close from k
    periods ago (no lookahead), and RSI confirming momentum.  The 4h timeframe makes
    this one of the most reliable trend filters available in technical analysis.

    Recommended pairs (strongly trending large/mid caps):
        ETH/USDT, SOL/USDT, AVAX/USDT, LINK/USDT, ARB/USDT
    """

    timeframe = "4h"
    startup_candle_count = 250

    minimal_roi = {
        "0": 0.12,
        "120": 0.06,
        "360": 0.03,
        "720": 0.0,
    }
    stoploss = -0.10
    trailing_stop = True
    trailing_stop_positive = 0.025
    trailing_stop_positive_offset = 0.05
    trailing_only_offset_is_reached = True

    buy_tenkan = IntParameter(7, 12, default=9, space="buy", optimize=True)
    buy_kijun = IntParameter(20, 30, default=26, space="buy", optimize=True)
    buy_senkou_b = IntParameter(44, 60, default=52, space="buy", optimize=True)
    buy_rsi_min = IntParameter(45, 60, default=50, space="buy", optimize=True)
    buy_chikou_confirm = BooleanParameter(default=True, space="buy", optimize=True)
    buy_vol_sma = IntParameter(10, 30, default=20, space="buy", optimize=True)
    buy_vol_ratio = DecimalParameter(0.8, 1.5, decimals=1, default=1.0, space="buy", optimize=True)

    sell_rsi_bear = IntParameter(30, 50, default=40, space="sell", optimize=True)
    sell_cloud_entry = BooleanParameter(default=True, space="sell", optimize=True)
    sell_cross_trigger = CategoricalParameter(["tenkan_kijun", "none"], default="tenkan_kijun", space="sell", optimize=True)

    protect_cooldown = IntParameter(2, 24, default=12, space="protection", optimize=True)
    protect_stop_duration = IntParameter(4, 48, default=24, space="protection", optimize=True)
    protect_stop_lookback = IntParameter(12, 96, default=48, space="protection", optimize=True)
    protect_trade_limit = IntParameter(2, 6, default=3, space="protection", optimize=True)
    protect_use_stop_guard = BooleanParameter(default=True, space="protection", optimize=True)

    @property
    def protections(self):
        return self._base_protections()

    @staticmethod
    def _ichimoku_mid(high_series, low_series, period: int):
        return (high_series.rolling(period).max() + low_series.rolling(period).min()) / 2.0

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        for t in self.buy_tenkan.range:
            dataframe[f"tenkan_{t}"] = self._ichimoku_mid(dataframe["high"], dataframe["low"], int(t))

        for k in self.buy_kijun.range:
            dataframe[f"kijun_{k}"] = self._ichimoku_mid(dataframe["high"], dataframe["low"], int(k))

        for t in self.buy_tenkan.range:
            for k in self.buy_kijun.range:
                tenkan = dataframe[f"tenkan_{t}"]
                kijun = dataframe[f"kijun_{k}"]
                senkou_a = ((tenkan + kijun) / 2.0).shift(int(k))
                dataframe[f"senkou_a_{t}_{k}"] = senkou_a

        for b in self.buy_senkou_b.range:
            for k in self.buy_kijun.range:
                senkou_b = self._ichimoku_mid(
                    dataframe["high"], dataframe["low"], int(b)
                ).shift(int(k))
                dataframe[f"senkou_b_{b}_{k}"] = senkou_b

        for v in self.buy_vol_sma.range:
            dataframe[f"vol_sma_{v}"] = dataframe["volume"].rolling(int(v)).mean()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        t = self.buy_tenkan.value
        k = self.buy_kijun.value
        b = self.buy_senkou_b.value

        tenkan = dataframe[f"tenkan_{t}"]
        kijun = dataframe[f"kijun_{k}"]
        senkou_a = dataframe[f"senkou_a_{t}_{k}"]
        senkou_b = dataframe[f"senkou_b_{b}_{k}"]
        vol_avg = dataframe[f"vol_sma_{self.buy_vol_sma.value}"]

        cloud_top = senkou_a.combine(senkou_b, max)
        green_cloud = senkou_a > senkou_b

        chikou_vs_past = dataframe["close"] > dataframe["close"].shift(int(k))

        conditions = [
            dataframe["volume"] > 0,
            dataframe["close"] > cloud_top,
            green_cloud,
            tenkan > kijun,
            dataframe["rsi"] > self.buy_rsi_min.value,
            dataframe["volume"] >= vol_avg * self.buy_vol_ratio.value,
        ]

        if self.buy_chikou_confirm.value:
            conditions.append(chikou_vs_past)

        dataframe.loc[
            reduce(lambda x, y: x & y, conditions),
            ["enter_long", "enter_tag"],
        ] = (1, "ichimoku_trend")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        t = self.buy_tenkan.value
        k = self.buy_kijun.value
        b = self.buy_senkou_b.value

        tenkan = dataframe[f"tenkan_{t}"]
        kijun = dataframe[f"kijun_{k}"]
        senkou_a = dataframe[f"senkou_a_{t}_{k}"]
        senkou_b = dataframe[f"senkou_b_{b}_{k}"]
        cloud_bottom = senkou_a.combine(senkou_b, min)

        rsi_bearish = dataframe["rsi"] < self.sell_rsi_bear.value

        exit_cond = rsi_bearish

        if self.sell_cloud_entry.value:
            exit_cond = exit_cond | (dataframe["close"] < cloud_bottom)

        if self.sell_cross_trigger.value == "tenkan_kijun":
            exit_cond = exit_cond | (tenkan < kijun)

        dataframe.loc[
            (dataframe["volume"] > 0) & exit_cond,
            ["exit_long", "exit_tag"],
        ] = (1, "ichimoku_exit")

        return dataframe
