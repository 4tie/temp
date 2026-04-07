# MultiMa Strategy V2
from freqtrade.strategy import IntParameter, IStrategy
from pandas import DataFrame
import talib.abstract as ta
from functools import reduce


class MultiMa(IStrategy):
    INTERFACE_VERSION: int = 3

    buy_params = {
        "buy_ma_count": 3,
        "buy_ma_gap": 6,
    }

    sell_params = {
        "sell_ma_count": 10,
        "sell_ma_gap": 50,
    }

    minimal_roi = {
        "0": 0.4,
        "3600": 0.08,
        "7200": 0.04,
        "14400": 0
    }

    stoploss = -0.01

    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.0
    trailing_only_offset_is_reached = False

    timeframe = "5m"
    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count = 820

    count_max = 20
    gap_max = 100

    buy_ma_count = IntParameter(1, count_max, default=3, space="buy")
    buy_ma_gap = IntParameter(1, gap_max, default=6, space="buy")

    sell_ma_count = IntParameter(1, count_max, default=10, space="sell")
    sell_ma_gap = IntParameter(1, gap_max, default=50, space="sell")

    @staticmethod
    def ma_col(period: int) -> str:
        return f"tema_{period}"

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        needed_periods = set()

        for ma_count in range(self.buy_ma_count.value + 1):
            period = ma_count * self.buy_ma_gap.value
            if period > 1:
                needed_periods.add(period)

        for ma_count in range(self.sell_ma_count.value + 1):
            period = ma_count * self.sell_ma_gap.value
            if period > 1:
                needed_periods.add(period)

        for period in sorted(needed_periods):
            col = self.ma_col(period)
            if col not in dataframe.columns:
                dataframe[col] = ta.TEMA(dataframe, timeperiod=int(period))

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []

        for ma_count in range(1, self.buy_ma_count.value):
            period = ma_count * self.buy_ma_gap.value
            past_period = (ma_count - 1) * self.buy_ma_gap.value

            if period <= 1 or past_period <= 1:
                continue

            key = self.ma_col(period)
            past_key = self.ma_col(past_period)

            if key in dataframe.columns and past_key in dataframe.columns:
                conditions.append(dataframe[key] < dataframe[past_key])

        if conditions:
            dataframe.loc[
                (reduce(lambda x, y: x & y, conditions) & (dataframe["volume"] > 0)),
                "enter_long"
            ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []

        for ma_count in range(1, self.sell_ma_count.value):
            period = ma_count * self.sell_ma_gap.value
            past_period = (ma_count - 1) * self.sell_ma_gap.value

            if period <= 1 or past_period <= 1:
                continue

            key = self.ma_col(period)
            past_key = self.ma_col(past_period)

            if key in dataframe.columns and past_key in dataframe.columns:
                conditions.append(dataframe[key] > dataframe[past_key])

        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x | y, conditions),
                "exit_long"
            ] = 1

        return dataframe