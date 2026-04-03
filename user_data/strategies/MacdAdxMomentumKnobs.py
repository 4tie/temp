from functools import reduce

import talib.abstract as ta
from pandas import DataFrame
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import BooleanParameter, CategoricalParameter, DecimalParameter, IntParameter

from BaseKnobStrategy import BaseKnobStrategy


class MacdAdxMomentumKnobs(BaseKnobStrategy):
    """
    Momentum strategy using MACD crossovers, ADX confirmation, RSI floor,
    and an EMA200 market bias filter.
    """

    minimal_roi = {
        "0": 0.10,
        "45": 0.05,
        "120": 0.02,
        "360": 0.0,
    }
    stoploss = -0.10
    startup_candle_count = 250

    buy_macd_fast = CategoricalParameter([8, 12], default=12, space="buy", optimize=True)
    buy_macd_slow = CategoricalParameter([21, 26, 35], default=26, space="buy", optimize=True)
    buy_macd_signal = CategoricalParameter([6, 9], default=9, space="buy", optimize=True)
    buy_adx = DecimalParameter(15.0, 35.0, decimals=1, default=22.0, space="buy", optimize=True)
    buy_rsi = IntParameter(45, 65, default=52, space="buy", optimize=True)
    buy_use_ema_filter = BooleanParameter(default=True, space="buy", optimize=True)

    sell_rsi = IntParameter(55, 85, default=72, space="sell", optimize=True)
    sell_on_cross = BooleanParameter(default=True, space="sell", optimize=True)

    protect_cooldown = IntParameter(2, 24, default=8, space="protection", optimize=True)
    protect_stop_duration = IntParameter(4, 48, default=12, space="protection", optimize=True)
    protect_stop_lookback = IntParameter(12, 96, default=24, space="protection", optimize=True)
    protect_trade_limit = IntParameter(2, 6, default=4, space="protection", optimize=True)
    protect_use_stop_guard = BooleanParameter(default=True, space="protection", optimize=True)

    @property
    def protections(self):
        return self._base_protections()

    @staticmethod
    def _macd_cols(fast: int, slow: int, signal: int):
        return (
            f"macd_{fast}_{slow}_{signal}",
            f"macdsignal_{fast}_{slow}_{signal}",
            f"macdhist_{fast}_{slow}_{signal}",
        )

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)

        for fast in self.buy_macd_fast.range:
            for slow in self.buy_macd_slow.range:
                if int(fast) >= int(slow):
                    continue
                for signal in self.buy_macd_signal.range:
                    macd = ta.MACD(
                        dataframe,
                        fastperiod=int(fast),
                        slowperiod=int(slow),
                        signalperiod=int(signal),
                    )
                    macd_col, signal_col, hist_col = self._macd_cols(int(fast), int(slow), int(signal))
                    dataframe[macd_col] = macd["macd"]
                    dataframe[signal_col] = macd["macdsignal"]
                    dataframe[hist_col] = macd["macdhist"]

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        macd_col, signal_col, hist_col = self._macd_cols(
            int(self.buy_macd_fast.value),
            int(self.buy_macd_slow.value),
            int(self.buy_macd_signal.value),
        )

        conditions = [
            dataframe["volume"] > 0,
            dataframe["adx"] > self.buy_adx.value,
            dataframe["rsi"] > self.buy_rsi.value,
            dataframe[hist_col] > 0,
            qtpylib.crossed_above(dataframe[macd_col], dataframe[signal_col]),
        ]

        if self.buy_use_ema_filter.value:
            conditions.append(dataframe["close"] > dataframe["ema200"])

        dataframe.loc[
            reduce(lambda x, y: x & y, conditions),
            ["enter_long", "enter_tag"],
        ] = (1, "macd_momentum")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        macd_col, signal_col, _ = self._macd_cols(
            int(self.buy_macd_fast.value),
            int(self.buy_macd_slow.value),
            int(self.buy_macd_signal.value),
        )

        exit_condition = dataframe["rsi"] > self.sell_rsi.value
        if self.sell_on_cross.value:
            exit_condition = exit_condition | qtpylib.crossed_below(dataframe[macd_col], dataframe[signal_col])

        dataframe.loc[
            (dataframe["volume"] > 0) & exit_condition,
            ["exit_long", "exit_tag"],
        ] = (1, "macd_exit")

        return dataframe
