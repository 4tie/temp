from functools import reduce

import talib.abstract as ta
from pandas import DataFrame

from freqtrade.strategy import IStrategy


class MultiMa2026HoldBase(IStrategy):
    INTERFACE_VERSION = 3
    can_short: bool = False

    timeframe = "5m"
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    startup_candle_count = 820

    minimal_roi = {
        "0": 0.523,
        "1553": 0.123,
        "2332": 0.076,
        "3169": 0,
    }

    stoploss = -0.345

    trailing_stop = False
    trailing_stop_positive = None
    trailing_stop_positive_offset = 0.0
    trailing_only_offset_is_reached = False

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

    buy_ma_count = 4
    buy_ma_gap = 8
    sell_ma_count = 12
    sell_ma_gap = 68

    @staticmethod
    def ma_col(period: int) -> str:
        return f"tema_{period}"

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
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
        conditions = []

        for ma_count in range(1, self.buy_ma_count):
            period = ma_count * self.buy_ma_gap
            past_period = (ma_count - 1) * self.buy_ma_gap

            if period <= 1 or past_period <= 1:
                continue

            key = self.ma_col(period)
            past_key = self.ma_col(past_period)
            if key in dataframe.columns and past_key in dataframe.columns:
                conditions.append(dataframe[key] < dataframe[past_key])

        if conditions:
            dataframe.loc[
                (reduce(lambda x, y: x & y, conditions) & (dataframe["volume"] > 0)),
                ["enter_long", "enter_tag"],
            ] = (1, "multima_hold_entry")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []

        for ma_count in range(1, self.sell_ma_count):
            period = ma_count * self.sell_ma_gap
            past_period = (ma_count - 1) * self.sell_ma_gap

            if period <= 1 or past_period <= 1:
                continue

            key = self.ma_col(period)
            past_key = self.ma_col(past_period)
            if key in dataframe.columns and past_key in dataframe.columns:
                conditions.append(dataframe[key] > dataframe[past_key])

        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x | y, conditions),
                ["exit_long", "exit_tag"],
            ] = (1, "multima_hold_exit")

        return dataframe


class MultiMa2026Hold8(MultiMa2026HoldBase):
    pass


class MultiMa2026Hold7(MultiMa2026HoldBase):
    buy_ma_gap = 7


class MultiMa2026Hold6(MultiMa2026HoldBase):
    buy_ma_gap = 6


class MultiMa2026Hold7Count3(MultiMa2026HoldBase):
    buy_ma_count = 3
    buy_ma_gap = 7


class MultiMa2026Hold8Exit64(MultiMa2026HoldBase):
    sell_ma_gap = 64


class MultiMa2026Hold7Exit64(MultiMa2026HoldBase):
    buy_ma_gap = 7
    sell_ma_gap = 64


class MultiMa2026Hold8Count5(MultiMa2026HoldBase):
    buy_ma_count = 5


class MultiMa2026Hold7Count5(MultiMa2026HoldBase):
    buy_ma_count = 5
    buy_ma_gap = 7


class MultiMa2026Hold6Exit64(MultiMa2026HoldBase):
    buy_ma_gap = 6
    sell_ma_gap = 64


class MultiMa2026Hold7Count3Exit64(MultiMa2026HoldBase):
    buy_ma_count = 3
    buy_ma_gap = 7
    sell_ma_gap = 64


class MultiMa2026Hold6Exit60(MultiMa2026HoldBase):
    buy_ma_gap = 6
    sell_ma_gap = 60


class MultiMa2026Hold7Exit60(MultiMa2026HoldBase):
    buy_ma_gap = 7
    sell_ma_gap = 60


class MultiMa2026Hold6Count3Exit64(MultiMa2026HoldBase):
    buy_ma_count = 3
    buy_ma_gap = 6
    sell_ma_gap = 64


class MultiMa2026Hold6Count3Exit60(MultiMa2026HoldBase):
    buy_ma_count = 3
    buy_ma_gap = 6
    sell_ma_gap = 60


class MultiMa2026Hold7Count3Exit56(MultiMa2026HoldBase):
    buy_ma_count = 3
    buy_ma_gap = 7
    sell_ma_gap = 56


class MultiMa2026HoldPack(MultiMa2026Hold8):
    """
    Default preset exposed under the pack filename for app-driven backtests.
    """

    pass
