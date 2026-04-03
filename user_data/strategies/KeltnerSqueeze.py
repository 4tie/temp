from functools import reduce

import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import BooleanParameter, CategoricalParameter, DecimalParameter, IntParameter

from BaseKnobStrategy import BaseKnobStrategy


class KeltnerSqueeze(BaseKnobStrategy):
    """
    Volatility squeeze breakout strategy on the 15m timeframe.

    Detects when Bollinger Bands contract inside Keltner Channels (a "squeeze"),
    then enters as momentum turns positive and the bands expand.  Squeeze setups
    are among the highest-probability breakout patterns because they signal the
    market is coiling energy before a directional move.

    Recommended pairs (mid-cap alts with periodic squeezes):
        LINK/USDT, AVAX/USDT, DOT/USDT, MATIC/USDT, NEAR/USDT
    """

    timeframe = "15m"
    startup_candle_count = 250

    minimal_roi = {
        "0": 0.07,
        "30": 0.035,
        "90": 0.015,
        "240": 0.0,
    }
    stoploss = -0.08
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    buy_bb_period = IntParameter(14, 25, default=20, space="buy", optimize=True)
    buy_bb_std = DecimalParameter(1.5, 2.5, decimals=1, default=2.0, space="buy", optimize=True)
    buy_kc_period = IntParameter(14, 25, default=20, space="buy", optimize=True)
    buy_kc_atr_mult = DecimalParameter(1.0, 2.5, decimals=1, default=1.5, space="buy", optimize=True)
    buy_adx_min = DecimalParameter(15.0, 35.0, decimals=1, default=20.0, space="buy", optimize=True)
    buy_mom_period = IntParameter(8, 20, default=12, space="buy", optimize=True)
    buy_require_vol_confirm = BooleanParameter(default=True, space="buy", optimize=True)
    buy_vol_ratio = DecimalParameter(1.1, 2.0, decimals=1, default=1.3, space="buy", optimize=True)

    sell_adx_min = DecimalParameter(10.0, 25.0, decimals=1, default=15.0, space="sell", optimize=True)
    sell_mom_exit = BooleanParameter(default=True, space="sell", optimize=True)
    sell_kc_band = CategoricalParameter(["upper", "extreme"], default="upper", space="sell", optimize=True)

    protect_cooldown = IntParameter(2, 24, default=6, space="protection", optimize=True)
    protect_stop_duration = IntParameter(4, 48, default=10, space="protection", optimize=True)
    protect_stop_lookback = IntParameter(12, 96, default=24, space="protection", optimize=True)
    protect_trade_limit = IntParameter(2, 6, default=4, space="protection", optimize=True)
    protect_use_stop_guard = BooleanParameter(default=True, space="protection", optimize=True)

    @property
    def protections(self):
        return self._base_protections()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)

        for mom_p in self.buy_mom_period.range:
            dataframe[f"mom_{mom_p}"] = ta.MOM(dataframe, timeperiod=int(mom_p))

        for vol_sma_p in [20]:
            dataframe[f"vol_sma_{vol_sma_p}"] = dataframe["volume"].rolling(vol_sma_p).mean()

        for bb_p in self.buy_bb_period.range:
            mid = dataframe["close"].rolling(int(bb_p)).mean()
            std = dataframe["close"].rolling(int(bb_p)).std(ddof=0)
            for bb_s in self.buy_bb_std.range:
                tag = f"bb_{bb_p}_{str(bb_s).replace('.', '_')}"
                dataframe[f"{tag}_upper"] = mid + std * float(bb_s)
                dataframe[f"{tag}_lower"] = mid - std * float(bb_s)
                dataframe[f"{tag}_width"] = dataframe[f"{tag}_upper"] - dataframe[f"{tag}_lower"]

        for kc_p in self.buy_kc_period.range:
            kc_ema = ta.EMA(dataframe, timeperiod=int(kc_p))
            kc_atr = ta.ATR(dataframe, timeperiod=int(kc_p))
            for kc_m in self.buy_kc_atr_mult.range:
                tag = f"kc_{kc_p}_{str(kc_m).replace('.', '_')}"
                dataframe[f"{tag}_upper"] = kc_ema + kc_atr * float(kc_m)
                dataframe[f"{tag}_lower"] = kc_ema - kc_atr * float(kc_m)
                dataframe[f"{tag}_width"] = dataframe[f"{tag}_upper"] - dataframe[f"{tag}_lower"]

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        bb_s = self.buy_bb_std.value
        kc_m = self.buy_kc_atr_mult.value
        bb_tag = f"bb_{self.buy_bb_period.value}_{str(bb_s).replace('.', '_')}"
        kc_tag = f"kc_{self.buy_kc_period.value}_{str(kc_m).replace('.', '_')}"
        mom_col = f"mom_{self.buy_mom_period.value}"

        squeeze = dataframe[f"{bb_tag}_width"] < dataframe[f"{kc_tag}_width"]
        mom_positive = dataframe[mom_col] > 0
        mom_rising = dataframe[mom_col] > dataframe[mom_col].shift(1)

        adx_rising = dataframe["adx"] > dataframe["adx"].shift(1)

        conditions = [
            dataframe["volume"] > 0,
            squeeze,
            mom_positive,
            mom_rising,
            dataframe["adx"] > self.buy_adx_min.value,
            adx_rising,
            dataframe["close"] > dataframe[f"{kc_tag}_upper"].shift(1),
        ]

        if self.buy_require_vol_confirm.value:
            conditions.append(dataframe["volume"] > dataframe["vol_sma_20"] * self.buy_vol_ratio.value)

        dataframe.loc[
            reduce(lambda x, y: x & y, conditions),
            ["enter_long", "enter_tag"],
        ] = (1, "keltner_squeeze_break")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        kc_m = self.buy_kc_atr_mult.value
        kc_tag = f"kc_{self.buy_kc_period.value}_{str(kc_m).replace('.', '_')}"
        mom_col = f"mom_{self.buy_mom_period.value}"

        if self.sell_kc_band.value == "extreme":
            upper_mult = float(kc_m) * 1.5
            extreme_upper = (
                ta.EMA(dataframe, timeperiod=int(self.buy_kc_period.value))
                + ta.ATR(dataframe, timeperiod=int(self.buy_kc_period.value)) * upper_mult
            )
            hit_band = dataframe["close"] > extreme_upper
        else:
            hit_band = dataframe["close"] > dataframe[f"{kc_tag}_upper"]

        adx_drop = dataframe["adx"] < self.sell_adx_min.value

        exit_cond = hit_band | adx_drop
        if self.sell_mom_exit.value:
            mom_reversal = (dataframe[mom_col] < 0) & (dataframe[mom_col].shift(1) >= 0)
            exit_cond = exit_cond | mom_reversal

        dataframe.loc[
            (dataframe["volume"] > 0) & exit_cond,
            ["exit_long", "exit_tag"],
        ] = (1, "keltner_exit")

        return dataframe
