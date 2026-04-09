class MultiMa_evo_g3(IStrategy):
    INTERFACE_VERSION: int = 3

    buy_params = {
        "buy_ma_count": 4,
        "buy_ma_gap": 6,
    }

    sell_params = {
        "sell_ma_count": 12,
        "sell_ma_gap": 40,
    }

    minimal_roi = {
        "0": 0.55,
        "1389": 0.18,
        "2073": 0.13,
        "2857": 0
    }

    stoploss = -0.015

    trailing_stop = True
    trailing_stop_positive = 0.04
    trailing_stop_positive_offset = 0.06
    trailing_only_offset_is_reached = False

# CHANGES: Adjusted buy and sell parameters to increase signal frequency, modified minimal ROI for a less aggressive drawdown, tightened stoploss for better risk management, and enabled trailing stop with a positive offset to capture more gains.