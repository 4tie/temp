from functools import reduce

import freqtrade.vendor.qtpylib.indicators as qtpylib
import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import IStrategy


class A15m(IStrategy):
    """
    30m trend-following pullback strategy with regime filter.

    Entry: shallow pullback (close between EMA9 and EMA21)
    during confirmed uptrend (all EMAs aligned, EMA200 rising).
    Exit: RSI overbought (>75).
    Risk: -3.5% SL, trailing 1.2%/2.5%, staged ROI.
    """

    INTERFACE_VERSION = 3
    can_short = False

    timeframe = "30m"
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    startup_candle_count = 250

    minimal_roi = {
        "0": 0.06,
        "60": 0.03,
        "180": 0.015,
        "480": 0,
    }

    stoploss = -0.045

    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.035
    trailing_only_offset_is_reached = True

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

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema9"] = ta.EMA(dataframe, timeperiod=9)
        dataframe["ema21"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema55"] = ta.EMA(dataframe, timeperiod=55)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)

        dataframe["trend_strong"] = (
            (dataframe["ema200"] > dataframe["ema200"].shift(20))
            & (dataframe["ema55"] > dataframe["ema200"])
            & (dataframe["ema21"] > dataframe["ema55"])
        ).astype("int8")

        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        macd = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe["macd"] = macd["macd"]
        dataframe["macd_signal"] = macd["macdsignal"]
        dataframe["macd_hist"] = macd["macdhist"]

        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]

        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)

        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2.0)
        dataframe["bb_lower"] = bollinger["lower"]
        dataframe["bb_mid"] = bollinger["mid"]
        dataframe["bb_upper"] = bollinger["upper"]

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = [
            dataframe["volume"] > 0,
            dataframe["trend_strong"] == 1,
            dataframe["close"] > dataframe["ema200"],
            dataframe["ema9"] > dataframe["ema21"],
            dataframe["rsi"] > 42,
            dataframe["rsi"] < 56,
            dataframe["macd_hist"] > 0,
            dataframe["adx"] > 25,
            dataframe["close"] < dataframe["ema9"],
            dataframe["close"] > dataframe["ema21"],
            dataframe["close"] > dataframe["bb_lower"],
            dataframe["atr_pct"] > 0.003,
        ]

        dataframe.loc[
            reduce(lambda x, y: x & y, conditions),
            ["enter_long", "enter_tag"],
        ] = (1, "trend_pullback")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_condition = dataframe["rsi"] > 75

        dataframe.loc[
            (dataframe["volume"] > 0) & exit_condition,
            ["exit_long", "exit_tag"],
        ] = (1, "rsi_overbought")

        return dataframe
