from functools import reduce

import talib.abstract as ta
from pandas import DataFrame

from freqtrade.strategy import IStrategy


class MultiMaScalp2026Base(IStrategy):
    """
    MultiMa-style 5m scalp variant for the recent 2026 market slice.
    The preset subclasses below vary entry aggressiveness and exit speed.
    """

    INTERFACE_VERSION = 3
    can_short: bool = False

    timeframe = "5m"
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    startup_candle_count = 560

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    order_time_in_force = {
        "entry": "GTC",
        "exit": "GTC",
    }

    minimal_roi = {
        "0": 0.05,
        "40": 0.02,
        "120": 0.008,
        "240": 0.0,
    }

    stoploss = -0.08
    trailing_stop = False
    trailing_stop_positive = None
    trailing_stop_positive_offset = 0.0
    trailing_only_offset_is_reached = False

    buy_ma_count = 4
    buy_ma_gap = 8
    sell_ma_count = 10
    sell_ma_gap = 52
    buy_rsi_floor = 48
    buy_rsi_ceiling = 68
    buy_adx_floor = 16
    sell_rsi = 70

    @staticmethod
    def ma_col(period: int) -> str:
        return f"tema_{period}"

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)

        needed_periods = set()
        for ma_count in range(self.buy_ma_count + 1):
            period = ma_count * self.buy_ma_gap
            if period > 1:
                needed_periods.add(period)

        for ma_count in range(self.sell_ma_count + 1):
            period = ma_count * self.sell_ma_gap
            if period > 1:
                needed_periods.add(period)

        for period in sorted(needed_periods):
            col = self.ma_col(period)
            if col not in dataframe.columns:
                dataframe[col] = ta.TEMA(dataframe, timeperiod=int(period))

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ladder_conditions = []

        for ma_count in range(1, self.buy_ma_count):
            period = ma_count * self.buy_ma_gap
            past_period = (ma_count - 1) * self.buy_ma_gap

            if period <= 1 or past_period <= 1:
                continue

            key = self.ma_col(period)
            past_key = self.ma_col(past_period)
            if key in dataframe.columns and past_key in dataframe.columns:
                ladder_conditions.append(dataframe[key] < dataframe[past_key])

        conditions = [
            dataframe["volume"] > 0,
            dataframe["ema50"] > dataframe["ema200"],
            dataframe["close"] > dataframe["ema200"],
            dataframe["rsi"] > self.buy_rsi_floor,
            dataframe["rsi"] < self.buy_rsi_ceiling,
            dataframe["adx"] > self.buy_adx_floor,
        ]

        if ladder_conditions:
            conditions.append(reduce(lambda x, y: x & y, ladder_conditions))

        dataframe.loc[
            reduce(lambda x, y: x & y, conditions),
            ["enter_long", "enter_tag"],
        ] = (1, "multima_scalp_entry")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ladder_conditions = []

        for ma_count in range(1, self.sell_ma_count):
            period = ma_count * self.sell_ma_gap
            past_period = (ma_count - 1) * self.sell_ma_gap

            if period <= 1 or past_period <= 1:
                continue

            key = self.ma_col(period)
            past_key = self.ma_col(past_period)
            if key in dataframe.columns and past_key in dataframe.columns:
                ladder_conditions.append(dataframe[key] > dataframe[past_key])

        exit_condition = dataframe["rsi"] > self.sell_rsi
        if ladder_conditions:
            exit_condition = exit_condition | reduce(lambda x, y: x | y, ladder_conditions)

        dataframe.loc[
            (dataframe["volume"] > 0) & exit_condition,
            ["exit_long", "exit_tag"],
        ] = (1, "multima_scalp_exit")

        return dataframe


class MultiMaScalp2026Balanced(MultiMaScalp2026Base):
    buy_ma_count = 4
    buy_ma_gap = 8
    sell_ma_count = 10
    sell_ma_gap = 52


class MultiMaScalp2026Aggressive(MultiMaScalp2026Base):
    buy_ma_count = 4
    buy_ma_gap = 7
    sell_ma_count = 10
    sell_ma_gap = 52


class MultiMaScalp2026MoreTrades(MultiMaScalp2026Base):
    buy_ma_count = 4
    buy_ma_gap = 6
    sell_ma_count = 10
    sell_ma_gap = 52


class MultiMaScalp2026FastExit(MultiMaScalp2026Base):
    buy_ma_count = 4
    buy_ma_gap = 7
    sell_ma_count = 9
    sell_ma_gap = 40


class MultiMaScalp2026FastEntry(MultiMaScalp2026Base):
    buy_ma_count = 3
    buy_ma_gap = 7
    sell_ma_count = 10
    sell_ma_gap = 52
    buy_rsi_floor = 46
    buy_adx_floor = 14


class MultiMaScalp2026TightRisk(MultiMaScalp2026Base):
    buy_ma_count = 4
    buy_ma_gap = 7
    sell_ma_count = 9
    sell_ma_gap = 44
    minimal_roi = {
        "0": 0.04,
        "30": 0.016,
        "90": 0.006,
        "180": 0.0,
    }
    stoploss = -0.06


class MultiMaScalp2026(MultiMaScalp2026Balanced):
    """
    Default preset exposed under the pack filename for app-driven backtests.
    """

    pass
