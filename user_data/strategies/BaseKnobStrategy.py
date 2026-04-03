from freqtrade.strategy import IStrategy


class BaseKnobStrategy(IStrategy):
    """
    Shared defaults for the strategy pack.

    These are intentionally conservative defaults. Override in config or hyperopt.
    """

    INTERFACE_VERSION = 3
    can_short: bool = False

    timeframe = "5m"
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    startup_candle_count: int = 250

    minimal_roi = {
        "0": 0.10,
        "60": 0.04,
        "180": 0.02,
        "360": 0.0,
    }

    stoploss = -0.10
    trailing_stop = False

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

    def _base_protections(self):
        protections = []

        if hasattr(self, "protect_cooldown"):
            protections.append(
                {
                    "method": "CooldownPeriod",
                    "stop_duration_candles": int(self.protect_cooldown.value),
                }
            )

        if getattr(self, "protect_use_stop_guard", None) and self.protect_use_stop_guard.value:
            protections.append(
                {
                    "method": "StoplossGuard",
                    "lookback_period_candles": int(self.protect_stop_lookback.value),
                    "trade_limit": int(self.protect_trade_limit.value),
                    "stop_duration_candles": int(self.protect_stop_duration.value),
                    "only_per_pair": False,
                }
            )

        return protections