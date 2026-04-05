import json
from pathlib import Path

import talib.abstract as ta
from pandas import DataFrame

from freqtrade.strategy import IStrategy


class BaseStarterStrategy(IStrategy):
    """
    Simple starter strategy for Freqtrade.
    Reads adjustable parameters from:
    user_data/strategy_params.json
    """

    timeframe = "5m"
    can_short = False
    startup_candle_count = 60

    # قيم افتراضية احتياطية لو ملف JSON ما اشتغل
    minimal_roi = {
        "0": 0.03
    }
    stoploss = -0.10

    # هذه تتحدث بعد قراءة JSON
    ema_fast_period = 20
    ema_slow_period = 50
    rsi_buy_value = 30
    rsi_sell_value = 70

    @classmethod
    def load_params(cls):
        """
        Load strategy parameters from user_data/strategy_params.json
        """
        try:
            base_dir = Path(__file__).resolve().parents[1]   # user_data
            params_path = base_dir / "strategy_params.json"

            with open(params_path, "r", encoding="utf-8") as f:
                params = json.load(f)

            cls.ema_fast_period = int(params.get("ema_fast", 20))
            cls.ema_slow_period = int(params.get("ema_slow", 50))
            cls.rsi_buy_value = int(params.get("rsi_buy", 30))
            cls.rsi_sell_value = int(params.get("rsi_sell", 70))
            cls.stoploss = float(params.get("stoploss", -0.10))
            cls.minimal_roi = {
                "0": float(params.get("roi", 0.03))
            }

            print(f"[BaseStarterStrategy] Loaded params from {params_path}")
            print(
                f"ema_fast={cls.ema_fast_period}, "
                f"ema_slow={cls.ema_slow_period}, "
                f"rsi_buy={cls.rsi_buy_value}, "
                f"rsi_sell={cls.rsi_sell_value}, "
                f"roi={cls.minimal_roi['0']}, "
                f"stoploss={cls.stoploss}"
            )

        except Exception as e:
            print(f"[BaseStarterStrategy] Failed to load JSON params: {e}")
            print("[BaseStarterStrategy] Using fallback default values.")


# حمّل القيم مرة عند تشغيل الملف
BaseStarterStrategy.load_params()


class BaseStarterStrategy(BaseStarterStrategy):
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast_period)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow_period)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["volume_mean_20"] = dataframe["volume"].rolling(20).mean()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe["ema_fast"] > dataframe["ema_slow"]) &
                (dataframe["rsi"] < self.rsi_buy_value) &
                (dataframe["volume"] > dataframe["volume_mean_20"]) &
                (dataframe["volume"] > 0)
            ),
            "enter_long"
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe["ema_fast"] < dataframe["ema_slow"]) |
                (dataframe["rsi"] > self.rsi_sell_value)
            ),
            "exit_long"
        ] = 1

        return dataframe