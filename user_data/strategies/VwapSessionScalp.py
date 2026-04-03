from functools import reduce

import numpy as np
import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import BooleanParameter, CategoricalParameter, DecimalParameter, IntParameter

from BaseKnobStrategy import BaseKnobStrategy


class VwapSessionScalp(BaseKnobStrategy):
    """
    VWAP + volume-spike scalping strategy on the 5m timeframe.

    Captures intraday mean-reversion to VWAP — a level that acts as a magnet for
    institutional order flow.  Price crossing above VWAP from below, accompanied by
    a volume spike and a neutral-to-bullish RSI, provides a high-probability long entry.

    Recommended pairs (high-volume majors with tight spreads):
        BTC/USDT, ETH/USDT, BNB/USDT, SOL/USDT, XRP/USDT
    """

    timeframe = "5m"
    startup_candle_count = 250

    minimal_roi = {
        "0": 0.04,
        "15": 0.02,
        "45": 0.01,
        "120": 0.0,
    }
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    buy_ema_trend = IntParameter(30, 100, default=50, space="buy", optimize=True)
    buy_vol_sma = IntParameter(10, 40, default=20, space="buy", optimize=True)
    buy_vol_ratio = DecimalParameter(1.2, 2.5, decimals=1, default=1.5, space="buy", optimize=True)
    buy_rsi_min = IntParameter(30, 50, default=40, space="buy", optimize=True)
    buy_rsi_max = IntParameter(55, 75, default=60, space="buy", optimize=True)
    buy_require_cross = BooleanParameter(default=True, space="buy", optimize=True)

    sell_rsi = IntParameter(60, 85, default=72, space="sell", optimize=True)
    sell_below_vwap = BooleanParameter(default=True, space="sell", optimize=True)
    sell_exit_mode = CategoricalParameter(["vwap_or_rsi", "vwap_and_rsi", "rsi_only"], default="vwap_or_rsi", space="sell", optimize=True)

    protect_cooldown = IntParameter(2, 24, default=4, space="protection", optimize=True)
    protect_stop_duration = IntParameter(4, 48, default=8, space="protection", optimize=True)
    protect_stop_lookback = IntParameter(12, 96, default=24, space="protection", optimize=True)
    protect_trade_limit = IntParameter(2, 6, default=3, space="protection", optimize=True)
    protect_use_stop_guard = BooleanParameter(default=True, space="protection", optimize=True)

    @property
    def protections(self):
        return self._base_protections()

    @staticmethod
    def _calc_vwap(dataframe: DataFrame) -> DataFrame:
        """
        Session VWAP anchored to day boundaries.
        Cumulative (price * volume) / cumulative volume, reset each calendar day.
        """
        tp = (dataframe["high"] + dataframe["low"] + dataframe["close"]) / 3.0
        pv = tp * dataframe["volume"]

        # Use date portion of the index to group by day
        if hasattr(dataframe.index, "date"):
            date_key = dataframe.index.date
        else:
            date_key = dataframe.index // (24 * 3600 * 1e9)

        cum_pv = pv.groupby(date_key).cumsum()
        cum_vol = dataframe["volume"].groupby(date_key).cumsum()
        vwap = cum_pv / cum_vol.replace(0, np.nan)
        return vwap

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["vwap"] = self._calc_vwap(dataframe)

        # Upper/lower VWAP bands using rolling std of typical price
        tp = (dataframe["high"] + dataframe["low"] + dataframe["close"]) / 3.0
        tp_std = tp.rolling(20).std(ddof=0)
        dataframe["vwap_upper"] = dataframe["vwap"] + 2.0 * tp_std

        for val in self.buy_ema_trend.range:
            dataframe[f"ema_trend_{val}"] = ta.EMA(dataframe, timeperiod=int(val))

        for val in self.buy_vol_sma.range:
            dataframe[f"vol_sma_{val}"] = dataframe["volume"].rolling(int(val)).mean()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema = dataframe[f"ema_trend_{self.buy_ema_trend.value}"]
        vol_avg = dataframe[f"vol_sma_{self.buy_vol_sma.value}"]

        conditions = [
            dataframe["volume"] > 0,
            dataframe["close"] > dataframe["vwap"],
            dataframe["volume"] > vol_avg * self.buy_vol_ratio.value,
            dataframe["rsi"] > self.buy_rsi_min.value,
            dataframe["rsi"] < self.buy_rsi_max.value,
            dataframe["close"] > ema,
        ]

        if self.buy_require_cross.value:
            conditions.append(dataframe["close"].shift(1) < dataframe["vwap"].shift(1))

        dataframe.loc[
            reduce(lambda x, y: x & y, conditions),
            ["enter_long", "enter_tag"],
        ] = (1, "vwap_cross_volume")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_overbought = dataframe["rsi"] > self.sell_rsi.value
        below_vwap = (dataframe["close"] < dataframe["vwap"]) if self.sell_below_vwap.value else rsi_overbought
        above_upper_band = dataframe["close"] > dataframe["vwap_upper"]

        if self.sell_exit_mode.value == "vwap_and_rsi":
            exit_cond = (rsi_overbought & below_vwap) | above_upper_band
        elif self.sell_exit_mode.value == "rsi_only":
            exit_cond = rsi_overbought | above_upper_band
        else:
            exit_cond = rsi_overbought | below_vwap | above_upper_band

        dataframe.loc[
            (dataframe["volume"] > 0) & exit_cond,
            ["exit_long", "exit_tag"],
        ] = (1, "vwap_exit")

        return dataframe
