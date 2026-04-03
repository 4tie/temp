from functools import reduce

import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import BooleanParameter, CategoricalParameter, DecimalParameter, IntParameter

from BaseKnobStrategy import BaseKnobStrategy


class PivotPointBounce(BaseKnobStrategy):
    """
    Classic Pivot Point support-bounce strategy on the 30m timeframe.

    Computes daily Classic Pivot Points (PP, S1, S2, R1, R2) from the *previous*
    candle's session high/low/close.  A long trade is triggered when price bounces
    off S1 or S2 (within one ATR) with RSI turning up from below 40 and the MACD
    histogram flipping positive.  Pivot levels are self-fulfilling — they are watched
    by institutions and retail alike, producing reliable bounce reactions.

    Recommended pairs (stable, high-volume pairs with clear OHLC structure):
        BTC/USDT, ETH/USDT, BNB/USDT, SOL/USDT, XRP/USDT
    """

    timeframe = "30m"
    startup_candle_count = 250

    minimal_roi = {
        "0": 0.06,
        "30": 0.03,
        "90": 0.015,
        "300": 0.0,
    }
    stoploss = -0.07
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    buy_atr_period = IntParameter(10, 20, default=14, space="buy", optimize=True)
    buy_atr_mult = DecimalParameter(0.5, 2.0, decimals=1, default=1.0, space="buy", optimize=True)
    buy_rsi_max = IntParameter(30, 50, default=40, space="buy", optimize=True)
    buy_bounce_level = CategoricalParameter(["s1", "s2", "both"], default="both", space="buy", optimize=True)
    buy_require_macd_flip = BooleanParameter(default=True, space="buy", optimize=True)
    buy_rsi_rising_bars = IntParameter(1, 3, default=1, space="buy", optimize=True)

    sell_rsi_max = IntParameter(60, 85, default=72, space="sell", optimize=True)
    sell_target = CategoricalParameter(["pp", "r1"], default="pp", space="sell", optimize=True)
    sell_macd_exit = BooleanParameter(default=True, space="sell", optimize=True)

    protect_cooldown = IntParameter(2, 24, default=6, space="protection", optimize=True)
    protect_stop_duration = IntParameter(4, 48, default=10, space="protection", optimize=True)
    protect_stop_lookback = IntParameter(12, 96, default=24, space="protection", optimize=True)
    protect_trade_limit = IntParameter(2, 6, default=4, space="protection", optimize=True)
    protect_use_stop_guard = BooleanParameter(default=True, space="protection", optimize=True)

    @property
    def protections(self):
        return self._base_protections()

    @staticmethod
    def _classic_pivots(dataframe: DataFrame) -> tuple:
        """
        Compute Classic Pivot Points from the previous day's OHLC.

        Groups 30m candles by calendar date using the DatetimeIndex, computes daily
        high/low/close, then forward-fills so every 30m candle carries the pivot
        levels from the *preceding* daily session.  Requires a DatetimeIndex (standard
        for Freqtrade DataFrames).
        """
        date_str = dataframe.index.date
        daily_high = dataframe["high"].groupby(date_str).transform("max")
        daily_low = dataframe["low"].groupby(date_str).transform("min")
        daily_close = dataframe["close"].groupby(date_str).transform("last")

        pp_today = (daily_high + daily_low + daily_close) / 3.0
        s1_today = (pp_today * 2) - daily_high
        s2_today = pp_today - (daily_high - daily_low)
        r1_today = (pp_today * 2) - daily_low
        r2_today = pp_today + (daily_high - daily_low)

        candles_per_day = 48
        pp_prev = pp_today.shift(candles_per_day)
        s1_prev = s1_today.shift(candles_per_day)
        s2_prev = s2_today.shift(candles_per_day)
        r1_prev = r1_today.shift(candles_per_day)
        r2_prev = r2_today.shift(candles_per_day)

        return pp_prev, s1_prev, s2_prev, r1_prev, r2_prev

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        macd = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe["macd"] = macd["macd"]
        dataframe["macd_signal"] = macd["macdsignal"]
        dataframe["macd_hist"] = macd["macdhist"]

        for p in self.buy_atr_period.range:
            dataframe[f"atr_{p}"] = ta.ATR(dataframe, timeperiod=int(p))

        pp, s1, s2, r1, r2 = self._classic_pivots(dataframe)
        dataframe["pivot_pp"] = pp
        dataframe["pivot_s1"] = s1
        dataframe["pivot_s2"] = s2
        dataframe["pivot_r1"] = r1
        dataframe["pivot_r2"] = r2

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        atr = dataframe[f"atr_{self.buy_atr_period.value}"]
        tolerance = atr * self.buy_atr_mult.value

        near_s1 = (
            (dataframe["low"] <= dataframe["pivot_s1"] + tolerance)
            & (dataframe["close"] >= dataframe["pivot_s1"] - tolerance)
        )
        near_s2 = (
            (dataframe["low"] <= dataframe["pivot_s2"] + tolerance)
            & (dataframe["close"] >= dataframe["pivot_s2"] - tolerance)
        )

        if self.buy_bounce_level.value == "s1":
            near_support = near_s1
        elif self.buy_bounce_level.value == "s2":
            near_support = near_s2
        else:
            near_support = near_s1 | near_s2

        rsi_turning_up = (
            (dataframe["rsi"] < self.buy_rsi_max.value)
            & (dataframe["rsi"] > dataframe["rsi"].shift(int(self.buy_rsi_rising_bars.value)))
        )

        conditions = [
            dataframe["volume"] > 0,
            near_support,
            rsi_turning_up,
            dataframe["close"] > dataframe["pivot_s2"] - tolerance,
        ]

        if self.buy_require_macd_flip.value:
            macd_flip = (dataframe["macd_hist"] > 0) & (dataframe["macd_hist"].shift(1) <= 0)
            conditions.append(macd_flip)
        else:
            conditions.append(dataframe["macd_hist"] > 0)

        dataframe.loc[
            reduce(lambda x, y: x & y, conditions),
            ["enter_long", "enter_tag"],
        ] = (1, "pivot_bounce")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        target = dataframe["pivot_pp"] if self.sell_target.value == "pp" else dataframe["pivot_r1"]

        rsi_exit = dataframe["rsi"] > self.sell_rsi_max.value
        price_target = dataframe["close"] >= target

        exit_cond = rsi_exit | price_target

        if self.sell_macd_exit.value:
            macd_flip_neg = (dataframe["macd_hist"] < 0) & (dataframe["macd_hist"].shift(1) >= 0)
            exit_cond = exit_cond | macd_flip_neg

        dataframe.loc[
            (dataframe["volume"] > 0) & exit_cond,
            ["exit_long", "exit_tag"],
        ] = (1, "pivot_exit")

        return dataframe
