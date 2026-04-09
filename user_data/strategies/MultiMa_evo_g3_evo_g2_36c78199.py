class MultiMa_evo_g3(IStrategy):
    INTERFACE_VERSION: int = 3

    buy_params = {
        "buy_ma_count": 5,
        "buy_ma_gap": 7,
    }

    sell_params = {
        "sell_ma_count": 12,
        "sell_ma_gap": 40,
    }

    minimal_roi = {
        "0": 0.6,
        "1389": 0.15,
        "2173": 0.10,
        "2957": 0
    }

    stoploss = -0.03

    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = False

    # CHANGES: Adjusted sell parameters to increase signal frequency and tighten the minimal ROI for better drawdown management.